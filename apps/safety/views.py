import json
import math
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import SosIncident, EmergencyContact, FieldUnit, Alert
from zones.models import Zone, DensityRecord, LocationPing
from accounts.models import PilgrimProfile, AuditLog, NotificationEvent
from nusuk.models import NusukCard
from services.weather import get_live_makkah_weather

staff_required = user_passes_test(
    lambda user: user.is_authenticated and (
        user.is_staff
    ),
    login_url='/accounts/login/'
)

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

@login_required(login_url='/accounts/login/')
@require_POST
def api_trigger_sos(request):
    """
    Called when pilgrim taps an emergency number or presses SOS.
    Saves incident telemetry in database.
    """
    try:
        data = json.loads(request.body or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON payload.'}, status=400)
    try:
        category = data.get('category', 'GENERAL')
        lat = float(data.get('lat', 21.4198)) if data.get('lat') is not None else 21.4198
        lng = float(data.get('lng', 39.8715)) if data.get('lng') is not None else 39.8715
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid emergency payload.'}, status=400)
    valid_categories = {choice[0] for choice in SosIncident.CATEGORY_CHOICES}
    if category not in valid_categories:
        return JsonResponse({'status': 'error', 'message': 'Invalid emergency category.'}, status=400)
    if not (math.isfinite(lat) and math.isfinite(lng)) or not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({'status': 'error', 'message': 'Invalid coordinates.'}, status=400)
    emergency_number = '997' if category in {'MEDICAL', 'HEAT'} else ('998' if category == 'CRUSH' else '911')

    # Get pilgrim profile
    pilgrim = getattr(request.user, 'profile', None)
    if pilgrim is None or pilgrim.role != 'pilgrim':
        return JsonResponse({'status': 'error', 'message': 'A pilgrim account is required.'}, status=403)

    idempotency_key = str(data.get('idempotency_key', '')).strip()[:64]
    if idempotency_key:
        prior = SosIncident.objects.filter(pilgrim=pilgrim, idempotency_key=idempotency_key).first()
        if prior:
            return JsonResponse({'status': 'duplicate', 'incident_id': prior.id, 'emergency_number': prior.called_number,
                                 'emergency_call_url': f'tel:{prior.called_number}', 'group_leader_phone': '', 'group_leader_call_url': None})

    battery_level = None
    try:
        if data.get('battery_level') is not None:
            battery_level = int(data.get('battery_level'))
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid battery level.'}, status=400)
    if battery_level is not None and not 0 <= battery_level <= 100:
        return JsonResponse({'status': 'error', 'message': 'Invalid battery level.'}, status=400)

    from groups.models import GroupMembership
    membership = GroupMembership.objects.filter(
        pilgrim=pilgrim, is_active=True
    ).select_related('group__leader__user').first()
    leader_phone = membership.group.leader.phone if membership else ''
    leader_phone = ''.join(ch for ch in leader_phone if ch.isdigit() or ch == '+')

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

    notes_text = f"SOS recorded for manual call to {emergency_number}. {plausibility_tag}"
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
            'created_at': existing_incident.created_at.strftime('%H:%M:%S'),
            'emergency_number': emergency_number,
            'emergency_call_url': f'tel:{emergency_number}',
            'group_leader_phone': leader_phone,
            'group_leader_call_url': f'tel:{leader_phone}' if leader_phone else None,
        })

    incident = SosIncident.objects.create(
        pilgrim=pilgrim,
        category=category,
        lat=lat,
        lng=lng,
        zone=zone,
        battery_level=battery_level,
        called_number=emergency_number,
        status='OPEN',
        notes=notes_text.strip(),
        idempotency_key=idempotency_key,
    )

    # Notify only active, consented group members; delivery is best effort.
    from groups.models import GroupMembership, LocationShareGrant
    from services.push import send_notification
    recipients = GroupMembership.objects.filter(
        group__members__pilgrim=pilgrim, group__members__is_active=True,
        is_active=True,
    ).exclude(pilgrim=pilgrim).select_related('pilgrim__user').distinct()
    for membership in recipients:
        active_grant = LocationShareGrant.objects.filter(
            pilgrim=membership.pilgrim, trip__group=membership.group,
            enabled=True, consent_given=True, revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists()
        if not active_grant:
            continue
        event = NotificationEvent.objects.create(
            recipient=membership.pilgrim.user, event_type='SOS',
            payload={'title': 'HajjGuard SOS', 'body': f'Group member requested help ({category}).', 'data': {'incident_id': incident.id}},
        )
        send_notification(event)

    return JsonResponse({
        'status': 'success',
        'incident_id': incident.id,
        'category': incident.get_category_display(),
        'zone': zone.name_en if zone else 'Holy Sites Corridor',
        'created_at': incident.created_at.strftime('%H:%M:%S'),
        'emergency_number': emergency_number,
        'emergency_call_url': f'tel:{emergency_number}',
        'group_leader_phone': leader_phone,
        'group_leader_call_url': f'tel:{leader_phone}' if leader_phone else None,
    })

@staff_required
@require_POST
def api_resolve_incident_by_id(request, incident_id):
    """
    Resolves an active SOS incident by ID (URL parameter).
    """
    with transaction.atomic():
        incident = get_object_or_404(SosIncident.objects.select_for_update(), id=incident_id)
        if incident.status == 'RESOLVED':
            return JsonResponse({'status': 'already_resolved', 'incident_id': incident.id})
        incident.status = 'RESOLVED'
        incident.resolved_at = timezone.now()
        incident.save(update_fields=['status', 'resolved_at'])

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

@staff_required
@require_GET
def api_lookup_pilgrim(request):
    """
    Lost Pilgrim Instant Lookup:
    Accepts an exact opaque QR token or exact staff-controlled username
    and returns minimum recovery contact details.
    """
    query = request.GET.get('q', '').strip()
    if not query:
        return JsonResponse({'status': 'error', 'message': 'Query parameter required'}, status=400)

    # Exact token or exact username only. Never perform substring enumeration.
    card = NusukCard.objects.filter(qr_token=query, is_valid=True).select_related('pilgrim', 'campaign').first()
    if card is None:
        profile = PilgrimProfile.objects.filter(user__username__iexact=query).first()
        card = NusukCard.objects.filter(pilgrim=profile, is_valid=True).select_related('pilgrim', 'campaign').first() if profile else None

    if not card:
        AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target='LOST_LOOKUP_NOT_FOUND', ip_address=request.META.get('REMOTE_ADDR'))
        return JsonResponse({'status': 'not_found', 'message': 'No registered pilgrim found matching query.'})

    profile = card.pilgrim
    camp = card.campaign
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'Pilgrim #{profile.id}', ip_address=request.META.get('REMOTE_ADDR'))

    return JsonResponse({
        'status': 'found',
        'pilgrim': {
            'name': profile.user.get_full_name() or profile.user.username,
            'emergency_contact': f"{profile.emergency_contact_name} ({profile.emergency_contact_phone})" if profile.emergency_contact_name else None,
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

@staff_required
@require_POST
def api_sync_haramain(request):
    """
    Refreshes the local synthetic Haram telemetry demonstration dataset.
    """
    from services.haramain_adapter import HaramainLiveAdapter
    result = HaramainLiveAdapter.sync_to_database()
    return JsonResponse(result)


@staff_required
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


@staff_required
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

    with transaction.atomic():
        incident = get_object_or_404(SosIncident.objects.select_for_update(), id=incident_id)
        unit = get_object_or_404(FieldUnit.objects.select_for_update(), id=unit_id)
        if incident.status not in {'OPEN', 'RESPONDING'}:
            return JsonResponse({'status': 'error', 'message': 'Incident is not assignable.'}, status=409)
        if not unit.available and incident.assigned_unit_id != unit.id:
            return JsonResponse({'status': 'error', 'message': 'Field unit is unavailable.'}, status=409)

        incident.assigned_unit = unit
        incident.status = 'RESPONDING'
        incident.save(update_fields=['assigned_unit', 'status'])

        unit.available = False
        unit.save(update_fields=['available'])

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


@staff_required
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

    with transaction.atomic():
        incident = get_object_or_404(SosIncident.objects.select_for_update(), id=incident_id)
        if incident.status == 'RESOLVED':
            return JsonResponse({'status': 'already_resolved', 'incident_id': incident.id})
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
        'accuracy_rating': 'Synthetic demonstration estimate; field accuracy not measured',
        'sections': matrix
    })


@staff_required
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


