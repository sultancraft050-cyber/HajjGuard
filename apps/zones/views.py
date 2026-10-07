import json
import math
from datetime import datetime, timezone as dt_timezone
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import Zone, Corridor, LocationPing, DensityRecord, VisitorPlace
from .utils import determine_zone_for_point, haversine_distance, altitude_from_barometric_pressure
from accounts.models import PilgrimProfile

def landing_home(request):
    """
    Renders the modern Burak-inspired Landing Page for HajjGuard.
    Features the interactive aerial Al-Masjid Al-Haram visual explorer,
    real-time 7-section crowd telemetry, live weather HUD, and dual-portal entry points.
    """
    from services.sectional_telemetry import HaramSectionalEngine
    from services.weather import get_live_makkah_weather
    from django.core.serializers.json import DjangoJSONEncoder

    sections = HaramSectionalEngine.get_sectional_status_matrix()
    weather = get_live_makkah_weather()

    total_headcount = sum(s['headcount'] for s in sections)
    total_capacity = sum(s['safe_capacity'] for s in sections)

    context = {
        'sections': sections,
        'sections_json': json.dumps(sections, cls=DjangoJSONEncoder),
        'weather': weather,
        'total_headcount': total_headcount,
        'total_capacity': total_capacity,
        'mataf_section': next((s for s in sections if s['code'] == 'Z-HARAM-MATAF'), None),
        'journey_zones': Zone.objects.all().order_by('site_type', 'name_en'),
    }
    return render(request, 'home.html', context)


def discover_makkah_view(request):
    """Public visitor directory for planning a wider Makkah trip.

    Entries are planning categories and source-labelled places, not live inventory.
    Booking, pricing, and availability stay with the visitor's chosen provider.
    """
    places = []
    for place in VisitorPlace.objects.filter(enabled=True).order_by('category', 'name_en'):
        try:
            place.full_clean()
        except Exception:
            continue
        places.append(place)
    from django.db.models import Q
    query = request.GET.get('q', '').strip().casefold()
    category = request.GET.get('category', '').upper()
    places = [p for p in places if (not category or p.category == category) and (not query or query in (p.name_en + p.name_ar + p.description + p.area).casefold())]
    categories = [{'code': code, 'label': label} for code, label in VisitorPlace.CATEGORY_CHOICES]
    return render(request, 'zones/discover_makkah.html', {'places': places, 'categories': categories})


@require_GET
def api_visitor_places(request):
    """Return only enabled, source-labelled public visitor directory records."""
    rows = VisitorPlace.objects.filter(enabled=True)
    category = request.GET.get('category', '').strip().upper()
    area = request.GET.get('area', '').strip()
    accessible = request.GET.get('accessible') == '1'
    query = request.GET.get('q', '').strip()
    if category:
        rows = rows.filter(category=category)
    if area:
        rows = rows.filter(area__icontains=area)
    if query:
        from django.db.models import Q
        rows = rows.filter(Q(name_en__icontains=query) | Q(name_ar__icontains=query) | Q(description__icontains=query) | Q(area__icontains=query))
    data = []
    for place in rows:
        try:
            place.full_clean()
        except Exception:
            continue
        has_accessibility = isinstance(place.accessibility, dict) and any(bool(v) for v in place.accessibility.values())
        if accessible and not has_accessibility:
            continue
        data.append({
            'id': place.id,
            'name_ar': place.name_ar,
            'name_en': place.name_en,
            'category': place.category,
            'description': place.description,
            'area': place.area,
            'coordinates': place.coordinates,
            'address': place.address,
            'accessibility': place.accessibility,
            'source': place.source,
            'source_url': place.source_url,
            'verification_date': place.verification_date.isoformat() if place.verification_date else None,
            'stale': place.is_stale,
            'provenance': 'admin_curated',
        })
    return JsonResponse({'places': data, 'note': 'Planning information. Verify current availability before visiting.'})


def live_map_view(request):
    """
    Renders the responsive full-screen Holy Sites Live Map
    """
    zones = Zone.objects.all().order_by('site_type', 'floor_level')
    return render(request, 'zones/live_map.html', {
        'zones': zones,
    })


@require_GET
def api_safety_features(request):
    from .models import SafetyMapFeature
    rows = SafetyMapFeature.objects.filter(enabled=True, verified_at__isnull=False)
    features = []
    for row in rows:
        from django.core.exceptions import ValidationError
        try:
            row.full_clean()
        except ValidationError:
            continue
        features.append({'id': row.pk, 'name': row.name, 'category': row.category,
                         'coordinates': row.coordinates, 'source': row.source, 'verified_at': row.verified_at})
    return JsonResponse({'features': features, 'note': 'Only source-labelled verified records are shown. Verify current availability on site.'})


@require_GET
def api_digital_twin(request):
    """Return the public, non-personal data needed by the 3D explorer."""
    zones = []
    for zone in Zone.objects.all().order_by('site_type', 'floor_level', 'name_en'):
        record = zone.density_records.first()
        stale = bool(record and not 0 <= (timezone.now() - record.timestamp).total_seconds() <= 1200)
        current = record if not stale else None
        zones.append({
            'code': zone.code,
            'name_ar': zone.name_ar,
            'name_en': zone.name_en,
            'site_type': zone.site_type,
            'center_lat': zone.center_lat,
            'center_lng': zone.center_lng,
            'radius_meters': zone.radius_meters,
            'floor_level': zone.floor_level,
            'density_per_sqm': current.density_per_sqm if current else None,
            'status': current.status if current else None,
            'predicted_density_20m': current.predicted_density_20m if current else None,
            'risk_score': current.risk_score if current else None,
            'data_timestamp': record.timestamp.isoformat() if record else None,
            'provenance': 'local_record' if record else 'unavailable',
            'stale': stale,
        })
    corridors = [{
        'id': corridor.pk,
        'name_en': corridor.name_en,
        'from_zone': corridor.from_zone.code,
        'to_zone': corridor.to_zone.code,
        'walking_minutes': corridor.base_walking_minutes,
        'width_meters': corridor.width_meters,
    } for corridor in Corridor.objects.filter(is_active=True).select_related('from_zone', 'to_zone')]
    places = []
    for place in VisitorPlace.objects.filter(enabled=True).order_by('name_en'):
        try:
            place.full_clean()
        except Exception:
            continue
        places.append({
            'id': place.pk, 'name_ar': place.name_ar, 'name_en': place.name_en,
            'category': place.category, 'coordinates': place.coordinates,
            'area': place.area, 'accessibility': place.accessibility,
            'stale': place.is_stale, 'source': place.source,
            'verification_date': place.verification_date.isoformat() if place.verification_date else None,
        })
    return JsonResponse({'zones': zones, 'corridors': corridors, 'places': places, 'mode': 'local_digital_twin'})

@require_GET
def api_zones_status(request):
    """
    Returns JSON array of all zones with their latest density, 
    capacity utilization, and color code (Green/Orange/Red)
    """
    zones = Zone.objects.all()
    results = []
    now = timezone.now()
    window_15m = now - timezone.timedelta(minutes=15)

    for z in zones:
        latest_record = z.density_records.first()
        base_people = latest_record.total_people if latest_record else 0
        
        # Real-time sensor fusion: Count distinct mobile devices transmitting in this zone in the last 15 mins
        live_active_devices = LocationPing.objects.filter(
            zone=z,
            timestamp__gte=window_15m
        ).values('pilgrim_id').distinct().count()

        current_people = max(base_people, live_active_devices)
        floor_area = max(z.floor_area_sqm, 1)
        density_sqm = round(current_people / floor_area, 2)
        pred_density = latest_record.predicted_density_20m if latest_record else round(density_sqm * 1.1, 2)
        risk_score = latest_record.risk_score if latest_record else min(100.0, round((current_people / max(z.safe_capacity, 1)) * 100.0, 1))

        status_code, color_code, status_label = z.get_status(current_people)
        capacity_ratio = round((current_people / max(z.safe_capacity, 1)) * 100, 1)

        observed_at = latest_record.timestamp if latest_record else None
        age_seconds = round((now - observed_at).total_seconds(), 1) if observed_at else None
        freshness = (
            'live' if age_seconds is not None and age_seconds <= 60 else
            'recent' if age_seconds is not None and age_seconds <= 900 else
            'stale' if age_seconds is not None else 'unavailable'
        )

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
            'observed_at': observed_at.isoformat() if observed_at else None,
            'data_age_seconds': age_seconds,
            'data_freshness': freshness,
            'data_source': 'density_record' if latest_record else 'telemetry_only',
        })

    corridors = []
    for corridor in Corridor.objects.filter(is_active=True).select_related('from_zone', 'to_zone'):
        from_zone = next((z for z in results if z['id'] == corridor.from_zone_id), None)
        to_zone = next((z for z in results if z['id'] == corridor.to_zone_id), None)
        if not from_zone or not to_zone:
            continue
        corridors.append({
            'id': corridor.id,
            'name_ar': corridor.name_ar,
            'name_en': corridor.name_en,
            'from_code': from_zone['code'],
            'to_code': to_zone['code'],
            'coordinates': [[from_zone['lat'], from_zone['lng']], [to_zone['lat'], to_zone['lng']]],
            'walking_minutes': corridor.base_walking_minutes,
            'width_meters': corridor.width_meters,
            'status': 'watch' if from_zone['status'] in ('RED', 'ORANGE') or to_zone['status'] in ('RED', 'ORANGE') else 'open',
        })

    return JsonResponse({'status': 'success', 'count': len(results), 'zones': results, 'corridors': corridors})

# Minimum throttling interval between pings per pilgrim (prevents device polling battery drain/DOS)
MIN_PING_INTERVAL_SECONDS = 3.0

@login_required(login_url='/accounts/login/')
@require_POST
def api_location_ping(request):
    """
    Telemetry ingest endpoint:
    Receives GPS coordinates from pilgrim device, validates boundaries and timestamps,
    applies throttling rate-limits, and assigns to the correct multi-level Zone.
    """
    try:
        data = json.loads(request.body)
        raw_lat = data.get('lat')
        raw_lng = data.get('lng')

        if raw_lat is None or raw_lng is None:
            return JsonResponse({'status': 'error', 'message': 'Missing lat or lng coordinate parameters'}, status=400)

        lat = float(raw_lat)
        lng = float(raw_lng)
    except (ValueError, TypeError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid latitude or longitude numerical values'}, status=400)

    # 1. Geographic Coordinate Boundary Validation
    if not (math.isfinite(lat) and math.isfinite(lng)) or not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
        return JsonResponse({'status': 'error', 'message': 'Coordinates out of physical bounds (-90..90, -180..180)'}, status=400)

    # 2. Multi-level floor and altitude parameters
    try:
        floor_level = int(data.get('floor_level', 0))
    except (ValueError, TypeError):
        floor_level = 0

    try:
        altitude = float(data.get('altitude')) if data.get('altitude') is not None else None
    except (ValueError, TypeError):
        altitude = None

    # Barometric pressure sensor fallback for 3D floor disambiguation
    if altitude is None and data.get('pressure_hpa') is not None:
        try:
            pressure_val = float(data.get('pressure_hpa'))
            altitude = altitude_from_barometric_pressure(pressure_val)
        except (ValueError, TypeError):
            pass

    try:
        accuracy_meters = float(data.get('accuracy_meters')) if data.get('accuracy_meters') is not None else None
        if accuracy_meters is not None and (not math.isfinite(accuracy_meters) or accuracy_meters < 0):
            return JsonResponse({'status': 'error', 'message': 'Invalid GPS accuracy'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid GPS accuracy'}, status=400)

    # 3. Spoofed Timestamp Protection
    client_ts_raw = data.get('timestamp')
    now = timezone.now()
    if client_ts_raw:
        try:
            if isinstance(client_ts_raw, (int, float)):
                # epoch timestamp in seconds or ms
                epoch = client_ts_raw / 1000.0 if client_ts_raw > 1e11 else client_ts_raw
                client_dt = datetime.fromtimestamp(epoch, tz=dt_timezone.utc)
            else:
                client_dt = datetime.fromisoformat(str(client_ts_raw).replace('Z', '+00:00'))

            delta = (client_dt - now).total_seconds()
            if delta > 60.0:  # More than 60s in the future
                return JsonResponse({'status': 'error', 'message': 'Spoofed telemetry timestamp: future time rejected'}, status=400)
            if delta < -86400.0:  # More than 24 hours in the past
                return JsonResponse({'status': 'error', 'message': 'Stale telemetry timestamp: older than 24 hours'}, status=400)
        except Exception:
            return JsonResponse({'status': 'error', 'message': 'Invalid telemetry timestamp'}, status=400)

    # 4. Resolve Pilgrim Profile
    pilgrim = getattr(request.user, 'profile', None)

    if not pilgrim:
        return JsonResponse({'status': 'error', 'message': 'A registered pilgrim profile is required'}, status=403)

    from groups.models import LocationShareGrant
    grant = LocationShareGrant.objects.filter(
        pilgrim=pilgrim, enabled=True, consent_given=True, revoked_at__isnull=True,
        consent_timestamp__isnull=False, expires_at__gt=now,
        trip__starts_at__lte=now, trip__ends_at__gt=now,
        trip__status__in=['PLANNED', 'ACTIVE'],
        trip__group__members__pilgrim=pilgrim, trip__group__members__is_active=True,
    ).first()
    if grant is None:
        return JsonResponse({'status': 'error', 'message': 'Active trip location consent is required.'}, status=403)

    # 5. Mobile Ingestion Throttling Check
    last_ping = LocationPing.objects.filter(pilgrim=pilgrim).order_by('-timestamp').first()
    if last_ping:
        elapsed = (now - last_ping.timestamp).total_seconds()
        if elapsed < MIN_PING_INTERVAL_SECONDS:
            return JsonResponse({
                'status': 'throttled',
                'message': f'Rate limit exceeded. Minimum interval {MIN_PING_INTERVAL_SECONDS}s',
                'retry_after_seconds': round(MIN_PING_INTERVAL_SECONDS - elapsed, 1)
            }, status=429)

    # 6. Multi-level Floor-Aware Zone Matching
    assigned_zone = determine_zone_for_point(lat, lng, floor_level=floor_level, max_search_radius=500.0)

    # Calculate distance to zone center for logging
    dist_to_center = None
    if assigned_zone:
        dist_to_center = round(haversine_distance(assigned_zone.center_lat, assigned_zone.center_lng, lat, lng), 1)

    ping = LocationPing.objects.create(
        pilgrim=pilgrim,
        lat=lat,
        lng=lng,
        accuracy_meters=accuracy_meters,
        altitude=altitude,
        floor_level=floor_level,
        zone=assigned_zone
    )
    from groups.pwa_views import evaluate_geofences
    evaluate_geofences(pilgrim, lat, lng)

    # Compute Adaptive Telemetry Engine parameters (Heartbeat interval & Jitter)
    rec = assigned_zone.density_records.first() if assigned_zone else None
    zone_density = rec.density_per_sqm if rec else 0.5
    is_dormant = (rec and rec.status == 'DORMANT')

    if assigned_zone and not is_dormant:
        if zone_density >= 2.0 or (rec and rec.status in ['RED', 'ORANGE']):
            adaptive_interval = 15.0  # High-density / choke corridor
        else:
            adaptive_interval = 45.0  # Normal active corridor
    else:
        adaptive_interval = 180.0     # Camp tent / hotel dormancy

    sampling_mode = 'DECIMATED' if (zone_density >= 3.5) else 'STANDARD'

    return JsonResponse({
        'status': 'success',
        'ping_id': ping.id,
        'zone_code': assigned_zone.code if assigned_zone else None,
        'zone_name_en': assigned_zone.name_en if assigned_zone else 'Outside Monitored Zones',
        'zone_name_ar': assigned_zone.name_ar if assigned_zone else 'خارج نطاق المشاعر المحددة',
        'floor_level': floor_level,
        'distance_to_center_meters': dist_to_center,
        'adaptive_telemetry': {
            'recommended_interval_seconds': adaptive_interval,
            'jitter_pct': 20.0,
            'sampling_mode': sampling_mode
        }
    })

def prune_stale_location_pings(older_than_hours=24):
    """
    Periodic Database Maintenance:
    Prunes raw location pings older than retention threshold to prevent database exhaustion.
    """
    cutoff = timezone.now() - timezone.timedelta(hours=older_than_hours)
    deleted_count, _ = LocationPing.objects.filter(timestamp__lt=cutoff).delete()
    return deleted_count


def zone_detail_view(request, zone_id):
    """
    KSU Specification Section 7.1 (Screen 4):
    Zone detail: Current density, predicted density, risk score with its breakdown.
    Feeds Section 8.3:
    'Show every term on the zone detail screen so the score can be questioned.'
    """
    if str(zone_id).isdigit():
        zone = get_object_or_404(Zone, id=int(zone_id))
    else:
        zone = get_object_or_404(Zone, code=zone_id)

    rec = zone.density_records.first()
    
    now = timezone.now()
    window_15m = now - timezone.timedelta(minutes=15)
    live_active = LocationPing.objects.filter(zone=zone, timestamp__gte=window_15m).values('pilgrim_id').distinct().count()
    base_people = rec.total_people if rec else 0
    current_people = max(base_people, live_active)

    # Vulnerable calculation (age >= 65)
    vulnerable_count = LocationPing.objects.filter(
        zone=zone,
        timestamp__gte=window_15m,
        pilgrim__age__gte=65
    ).values('pilgrim_id').distinct().count()
    if vulnerable_count == 0 and current_people > 0:
        vulnerable_count = int(current_people * 0.18)

    vulnerable_pct = round((vulnerable_count / max(current_people, 1)) * 100.0, 1)
    capacity_pct = round((current_people / max(zone.safe_capacity, 1)) * 100.0, 1)
    density_sqm = round(current_people / max(zone.floor_area_sqm, 1), 2)
    pred_density = rec.predicted_density_20m if rec else round(density_sqm * 1.08, 2)

    from services.weather import get_live_makkah_weather
    weather = get_live_makkah_weather()
    heat_index = weather.get('feels_like', 36)
    heat_penalty = min(100.0, max(0.0, (heat_index - 30) * 5.0))

    # Weight components (Section 3 F2)
    w_density = round(capacity_pct * 0.5, 1)
    w_vulnerability = round(vulnerable_pct * 0.3, 1)
    w_heat = round(heat_penalty * 0.2, 1)
    computed_risk = round(min(100.0, w_density + w_vulnerability + w_heat), 1)

    status_code, color_code, label = zone.get_status(current_people)

    from safety.models import Alert
    active_alerts = Alert.objects.filter(zone=zone, acknowledged=False)

    return render(request, 'zones/zone_detail.html', {
        'zone': zone,
        'current_people': current_people,
        'capacity_pct': capacity_pct,
        'density_sqm': density_sqm,
        'predicted_density_20m': pred_density,
        'vulnerable_count': vulnerable_count,
        'vulnerable_pct': vulnerable_pct,
        'heat_index': heat_index,
        'w_density': w_density,
        'w_vulnerability': w_vulnerability,
        'w_heat': w_heat,
        'computed_risk': computed_risk,
        'status_code': status_code,
        'color_code': color_code,
        'status_label': label,
        'active_alerts': active_alerts,
        'weather': weather,
    })


def guidance_view(request):
    """Public journey form; coordinates are ephemeral and never persisted."""
    from services.routing import RoutingEngine
    from_zone = request.GET.get('from', 'Z-MINA-SEC3')
    to_zone = request.GET.get('to', 'Z-JAMARAT-F0')
    comparison = RoutingEngine.get_route_comparison(from_zone, to_zone)
    return render(request, 'zones/guidance.html', {
        'journey_zones': Zone.objects.all().order_by('site_type', 'name_en'),
        'comparison': comparison,
    })
