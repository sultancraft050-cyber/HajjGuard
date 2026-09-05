import json
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils.translation import gettext as _
from .models import Zone, Corridor, LocationPing, DensityRecord
from accounts.models import PilgrimProfile

def live_map_view(request):
    """
    Renders the responsive full-screen Holy Sites Live Map
    """
    zones = Zone.objects.all().order_by('site_type', 'floor_level')
    return render(request, 'zones/live_map.html', {
        'zones': zones,
    })

@require_GET
def api_zones_status(request):
    """
    Returns JSON array of all zones with their latest density, 
    capacity utilization, and color code (Green/Orange/Red)
    """
    zones = Zone.objects.all()
    results = []

    for z in zones:
        latest_record = z.density_records.first()
        current_people = latest_record.total_people if latest_record else 150
        density_sqm = latest_record.density_per_sqm if latest_record else (current_people / z.floor_area_sqm)
        pred_density = latest_record.predicted_density_20m if latest_record else (density_sqm * 1.1)
        risk_score = latest_record.risk_score if latest_record else 15.0

        status_code, color_code, status_label = z.get_status(current_people)
        capacity_ratio = round((current_people / max(z.safe_capacity, 1)) * 100, 1)

        results.append({
            'id': z.id,
            'code': z.code,
            'name_ar': z.name_ar,
            'name_en': z.name_en,
            'site_type': z.site_type,
            'site_display': z.get_site_type_display(),
            'lat': z.center_lat,
            'lng': z.center_lng,
            'radius': z.radius_meters,
            'floor_level': z.floor_level,
            'safe_capacity': z.safe_capacity,
            'current_people': current_people,
            'capacity_pct': capacity_ratio,
            'density_sqm': round(density_sqm, 2),
            'predicted_density_20m': round(pred_density, 2),
            'risk_score': round(risk_score, 1),
            'status': status_code,
            'color': color_code,
            'status_label': str(status_label),
        })

    return JsonResponse({'status': 'success', 'count': len(results), 'zones': results})

@csrf_exempt
@require_POST
def api_location_ping(request):
    """
    Receives GPS coordinates from pilgrim device, finds which zone 
    they are currently inside, and records the ping.
    """
    try:
        data = json.loads(request.body)
        lat = float(data.get('lat'))
        lng = float(data.get('lng'))
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid latitude or longitude'}, status=400)

    # Resolve pilgrim profile if logged in, or fallback to first test pilgrim
    pilgrim = None
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        pilgrim = request.user.profile
    else:
        pilgrim = PilgrimProfile.objects.filter(role='pilgrim').first()

    if not pilgrim:
        return JsonResponse({'status': 'error', 'message': 'No pilgrim profile found'}, status=400)

    # Find which zone contains this point
    matched_zone = None
    closest_zone = None
    min_distance = float('inf')

    for z in Zone.objects.all():
        dist = z.distance_to(lat, lng)
        if dist < min_distance:
            min_distance = dist
            closest_zone = z
        if z.contains_point(lat, lng):
            matched_zone = z
            break

    # If not strictly inside any zone radius, assign to closest if within 500m
    assigned_zone = matched_zone if matched_zone else (closest_zone if min_distance <= 500 else None)

    ping = LocationPing.objects.create(
        pilgrim=pilgrim,
        lat=lat,
        lng=lng,
        zone=assigned_zone
    )

    return JsonResponse({
        'status': 'success',
        'ping_id': ping.id,
        'zone_code': assigned_zone.code if assigned_zone else None,
        'zone_name_en': assigned_zone.name_en if assigned_zone else 'Outside Monitored Zones',
        'zone_name_ar': assigned_zone.name_ar if assigned_zone else 'خارج نطاق المشاعر المحددة',
        'distance_to_center_meters': round(min_distance, 1) if closest_zone else None
    })
