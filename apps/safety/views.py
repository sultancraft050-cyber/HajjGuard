import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import SosIncident, EmergencyContact
from zones.models import Zone, DensityRecord
from accounts.models import PilgrimProfile
from nusuk.models import NusukCard

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
    for z in zones:
        rec = z.density_records.first()
        status_code, color_code, label = z.get_status(rec.total_people if rec else 100)
        ranked_zones.append({
            'zone': z,
            'record': rec,
            'status_code': status_code,
            'color': color_code,
            'status_label': label,
            'risk': rec.risk_score if rec else 15.0
        })
    ranked_zones.sort(key=lambda x: x['risk'], reverse=True)

    return render(request, 'safety/operations_dashboard.html', {
        'total_pilgrims': total_pilgrims,
        'active_incidents_count': active_incidents.count(),
        'incidents': active_incidents[:10],
        'highest_risk_zone': highest_risk_zone,
        'ranked_zones': ranked_zones,
    })

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

    # Find matching zone
    zone = None
    for z in Zone.objects.all():
        if z.contains_point(lat, lng):
            zone = z
            break

    incident = SosIncident.objects.create(
        pilgrim=pilgrim,
        category=category,
        lat=lat,
        lng=lng,
        zone=zone,
        called_number=called_number,
        status='OPEN',
        notes=f"Auto-logged via HajjGuard SOS trigger to {called_number}"
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
def api_resolve_incident(request, incident_id):
    """
    Resolves an active SOS incident from the operations queue
    """
    incident = get_object_or_404(SosIncident, id=incident_id)
    incident.status = 'RESOLVED'
    incident.resolved_at = timezone.now()
    incident.save()
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

