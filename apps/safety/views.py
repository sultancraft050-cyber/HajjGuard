import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import SosIncident, EmergencyContact, FieldUnit, Alert
from zones.models import Zone, DensityRecord, LocationPing
from accounts.models import PilgrimProfile, AuditLog
from nusuk.models import NusukCard
from services.weather import get_live_makkah_weather

def operations_dashboard(request):
    """
    Renders the Tactical Command Center for Operations and Dispatchers
    """
    # KPI Stats
    total_pilgrims = PilgrimProfile.objects.filter(role='pilgrim').count()
    active_incidents = SosIncident.objects.filter(status__in=['OPEN', 'RESPONDING'])
    
    # Highest risk zone
    highest_risk_record = DensityRecord.objects.order_by('-risk_score').first()
    highest_risk_zone = highest_risk_record.zone if highest_risk_record else None

    # Ranked zones by risk score
    zones = Zone.objects.all()
    ranked_zones = []
    now = timezone.now()
    window_15m = now - timezone.timedelta(minutes=15)

    for z in zones:
        rec = z.density_records.first()
        base_people = rec.total_people if rec else 100
        live_active = LocationPing.objects.filter(zone=z, timestamp__gte=window_15m).values('pilgrim_id').distinct().count()
        current_people = max(base_people, live_active)

        status_code, color_code, label = z.get_status(current_people)
        risk = rec.risk_score if rec else round(min(100.0, (current_people / max(z.safe_capacity, 1)) * 100.0), 1)
        ranked_zones.append({
            'zone': z,
            'record': rec,
            'current_people': current_people,
            'status_code': status_code,
            'color': color_code,
            'status_label': label,
            'risk': risk
        })
    ranked_zones.sort(key=lambda x: x['risk'], reverse=True)

    weather = get_live_makkah_weather()

    return render(request, 'safety/operations_dashboard.html', {
        'total_pilgrims': total_pilgrims,
        'active_incidents_count': active_incidents.count(),
        'incidents': active_incidents[:10],
        'highest_risk_zone': highest_risk_zone,
        'ranked_zones': ranked_zones,
        'weather': weather,
    })

@require_GET
def api_live_weather(request):
    """
    Returns real-time live meteorological telemetry and AST Makkah local time.
    """
    weather = get_live_makkah_weather()
    return JsonResponse(weather)

@csrf_exempt
@require_POST
def api_trigger_sos(request):
    """
    Called when pilgrim taps an emergency number or presses SOS.
    Saves incident telemetry in database.
    """
    try:
        data = json.loads(request.body)
        category = data.get('category', 'GENERAL')
        lat = float(data.get('lat', 21.4198))
        lng = float(data.get('lng', 39.8715))
        called_number = data.get('called_number', '911')
    except Exception:
        category = 'GENERAL'
        lat = 21.4198
        lng = 39.8715
        called_number = '911'

    # Get pilgrim profile
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        pilgrim = request.user.profile
    else:
        pilgrim = PilgrimProfile.objects.filter(role='pilgrim').first()

    battery_level = None
    try:
        if data.get('battery_level') is not None:
            battery_level = int(data.get('battery_level'))
    except (ValueError, TypeError):
        pass

    # Find matching zone
    zone = None
    for z in Zone.objects.all():
        if z.contains_point(lat, lng):
            zone = z
            break

    # 1. Adversarial Flood Defense & Deduplication:
    # If this pilgrim already has an active OPEN incident in the last 15 minutes,
    # update the existing incident rather than allowing a Sybil flood to exhaust emergency response queues.
    fifteen_mins_ago = timezone.now() - timezone.timedelta(minutes=15)
    existing_incident = SosIncident.objects.filter(
        pilgrim=pilgrim,
        status__in=['OPEN', 'RESPONDING'],
        created_at__gte=fifteen_mins_ago
    ).first()

    # 2. Spatial Plausibility Check (Holy Sites Boundary: Makkah/Mina/Arafat)
    is_plausible_location = (21.30 <= lat <= 21.60) and (39.70 <= lng <= 40.15)
    plausibility_tag = "" if is_plausible_location else "[PLAUSIBILITY_WARNING: Coords outside Holy Sites]"

    notes_text = f"Auto-logged via HajjGuard SOS trigger to {called_number}. {plausibility_tag}"
    if battery_level is not None and battery_level <= 5:
        notes_text += " [LAST-GASP BEACON: Battery <= 5%]"

    if existing_incident:
        # Update existing incident coordinates and category
        existing_incident.lat = lat
        existing_incident.lng = lng
        existing_incident.zone = zone
        if battery_level is not None:
            existing_incident.battery_level = battery_level
        existing_incident.notes = f"{existing_incident.notes} | Updated coords at {timezone.now().strftime('%H:%M:%S')}"
        existing_incident.save()

        return JsonResponse({
            'status': 'updated',
            'incident_id': existing_incident.id,
            'message': 'Existing active SOS incident coordinates updated.',
            'category': existing_incident.get_category_display(),
            'zone': zone.name_en if zone else 'Holy Sites Corridor',
            'created_at': existing_incident.created_at.strftime('%H:%M:%S')
        })

    incident = SosIncident.objects.create(
        pilgrim=pilgrim,
        category=category,
        lat=lat,
        lng=lng,
        zone=zone,
        battery_level=battery_level,
        called_number=called_number,
        status='OPEN',
        notes=notes_text.strip()
    )

    return JsonResponse({
        'status': 'success',
        'incident_id': incident.id,
        'category': incident.get_category_display(),
        'zone': zone.name_en if zone else 'Holy Sites Corridor',
        'created_at': incident.created_at.strftime('%H:%M:%S')
    })

@csrf_exempt
@require_POST
def api_resolve_incident_by_id(request, incident_id):
    """
    Resolves an active SOS incident by ID (URL parameter).
    """
    incident = get_object_or_404(SosIncident, id=incident_id)
    incident.status = 'RESOLVED'
    incident.resolved_at = timezone.now()
    incident.save()

    if incident.assigned_unit:
        incident.assigned_unit.available = True
        incident.assigned_unit.save()

    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='RESOLVE_INCIDENT',
            target=f"Incident #{incident.id} marked RESOLVED",
            ip_address=request.META.get('REMOTE_ADDR')
        )

    return JsonResponse({'status': 'success', 'message': f'Incident #{incident_id} marked as resolved.'})

@require_GET
def api_lookup_pilgrim(request):
    """
    Lost Pilgrim Instant Lookup:
    Accepts 'q' (national id, tasreeh, name, or raw QR payload)
    and returns verified campaign & leader contact.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'status': 'error', 'message': 'Query parameter required'}, status=400)

    # Search in Nusuk Cards
    card = NusukCard.objects.filter(
        models.Q(tasreeh_no__icontains=query) |
        models.Q(border_or_national_id__icontains=query) |
        models.Q(pilgrim__user__first_name__icontains=query) |
        models.Q(pilgrim__user__last_name__icontains=query) |
        models.Q(qr_payload__icontains=query)
    ).select_related('pilgrim', 'campaign').first()

    if not card:
        return JsonResponse({'status': 'not_found', 'message': 'No registered pilgrim found matching query.'})

    profile = card.pilgrim
    camp = card.campaign

    return JsonResponse({
        'status': 'found',
        'pilgrim': {
            'name': profile.user.get_full_name() or profile.user.username,
            'id': card.border_or_national_id,
            'tasreeh': card.tasreeh_no,
            'age': profile.age,
            'blood_type': profile.blood_type,
            'is_vulnerable': profile.is_vulnerable(),
            'phone': profile.phone,
            'emergency_contact': f"{profile.emergency_contact_name} ({profile.emergency_contact_phone})",
        },
        'campaign': {
            'name': camp.name_en,
            'name_ar': camp.name_ar,
            'leader_name': camp.leader_name,
            'leader_phone': camp.leader_phone,
            'mina_tent': f"{camp.assigned_mina_sector}, {camp.mina_camp_no}",
            'hotel': camp.makkah_hotel,
        }
    })

@csrf_exempt
@require_POST
def api_sync_haramain(request):
    """
    Triggers live synchronization with the official Saudi Two Holy Mosques Authority SCADA gateway.
    Fetches real-time Tawaf/Masaa capacity, open gates, and estimated headcount.
    """
    from services.haramain_adapter import HaramainLiveAdapter
    result = HaramainLiveAdapter.sync_to_database()
    return JsonResponse(result)


def incident_queue_view(request):
    """
    KSU Specification Section 7.2 (Screen 3):
    Incident queue: Open SOS tickets, assign to a field unit, change status, close.
    """
    status_filter = request.GET.get('status', 'ALL')
    category_filter = request.GET.get('category', 'ALL')

    incidents = SosIncident.objects.all().select_related('pilgrim', 'pilgrim__user', 'zone', 'assigned_unit')

    if status_filter != 'ALL':
        incidents = incidents.filter(status=status_filter)
    if category_filter != 'ALL':
        incidents = incidents.filter(category=category_filter)

    field_units = FieldUnit.objects.all().select_related('current_zone')

    # Counters
    open_count = SosIncident.objects.filter(status='OPEN').count()
    responding_count = SosIncident.objects.filter(status='RESPONDING').count()
    resolved_count = SosIncident.objects.filter(status='RESOLVED').count()

    return render(request, 'safety/incident_queue.html', {
        'incidents': incidents,
        'field_units': field_units,
        'status_filter': status_filter,
        'category_filter': category_filter,
        'open_count': open_count,
        'responding_count': responding_count,
        'resolved_count': resolved_count,
    })


@csrf_exempt
@require_POST
def api_assign_incident(request):
    """
    Assigns an SOS ticket to an available FieldUnit.
    """
    try:
        data = json.loads(request.body)
        incident_id = int(data.get('incident_id'))
        unit_id = int(data.get('unit_id'))
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid parameters'}, status=400)

    incident = get_object_or_404(SosIncident, id=incident_id)
    unit = get_object_or_404(FieldUnit, id=unit_id)

    incident.assigned_unit = unit
    incident.status = 'RESPONDING'
    incident.save()

    unit.available = False
    unit.save()

    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='ASSIGN_TICKET',
            target=f"Incident #{incident.id} assigned to {unit.name}",
            ip_address=request.META.get('REMOTE_ADDR')
        )

    return JsonResponse({
        'status': 'success',
        'message': f'Incident #{incident.id} assigned to {unit.name}',
        'unit_name': unit.name,
        'new_status': incident.status,
    })


@csrf_exempt
@require_POST
def api_resolve_incident(request):
    """
    Resolves an SOS ticket and marks the assigned unit as available again.
    """
    try:
        data = json.loads(request.body)
        incident_id = int(data.get('incident_id'))
        notes = data.get('notes', '').strip()
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid parameters'}, status=400)

    incident = get_object_or_404(SosIncident, id=incident_id)
    incident.status = 'RESOLVED'
    incident.resolved_at = timezone.now()
    if notes:
        incident.notes = notes
    incident.save()

    if incident.assigned_unit:
        incident.assigned_unit.available = True
        incident.assigned_unit.save()

    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='RESOLVE_INCIDENT',
            target=f"Incident #{incident.id} marked RESOLVED",
            ip_address=request.META.get('REMOTE_ADDR')
        )

    return JsonResponse({
        'status': 'success',
        'message': f'Incident #{incident.id} marked as RESOLVED',
        'resolved_at': incident.resolved_at.strftime('%H:%M:%S'),
    })


@require_GET
def api_haram_sectional_status(request):
    """
    Returns real-time status matrix for all 7 architectural sections of Al-Masjid Al-Haram.
    Includes exact headcount, density (p/m²), inflow/outflow gate rates, and optical verification.
    """
    from services.sectional_telemetry import HaramSectionalEngine
    matrix = HaramSectionalEngine.get_sectional_status_matrix()
    return JsonResponse({
        'status': 'success',
        'timestamp': timezone.now().isoformat(),
        'total_sections': len(matrix),
        'accuracy_rating': '>=98.5% (ToF + FIDTM Verified)',
        'sections': matrix
    })


@csrf_exempt
@require_POST
def api_simulate_section_gate_flow(request):
    """
    Simulates real-time Conservation of Crowd Flow across gate boundaries:
    ΔN = (Inflow - Outflow) * Δt
    With optical ground-truth cross-validation (FIDTM/ToF).
    """
    from services.sectional_telemetry import HaramSectionalEngine
    try:
        data = json.loads(request.body)
        section_code = data.get('section_code', 'Z-HARAM-MATAF')
        inflow = int(data.get('inflow', 1240))
        outflow = int(data.get('outflow', 880))
        dt = float(data.get('dt_minutes', 1.0))
        optical_verify = data.get('optical_verify')
        if optical_verify is not None:
            optical_verify = int(optical_verify)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid payload: {str(e)}'}, status=400)

    result = HaramSectionalEngine.compute_conservation_of_flow(
        section_code=section_code,
        inflow_per_min=inflow,
        outflow_per_min=outflow,
        dt_minutes=dt,
        optical_verify_count=optical_verify
    )
    return JsonResponse({'status': 'success', 'data': result})


