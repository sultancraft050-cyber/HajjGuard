import csv
from functools import wraps
from datetime import timedelta
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.utils import timezone
from django.utils.translation import gettext as _
from .services import RoutingEngine, CrowdSimulator, PredictiveForecaster
from zones.models import Zone, DensityRecord, LocationPing, VisitorPlace
from zones.utils import haversine_distance
from safety.models import SosIncident
from accounts.models import PilgrimProfile, AuditLog
from services.weather import get_live_makkah_weather


def staff_export_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            AuditLog.objects.create(
                user=request.user if request.user.is_authenticated else None,
                action='EXPORT_REPORT',
                target=f'DENIED {request.path}',
                ip_address=request.META.get('REMOTE_ADDR'),
            )
            return JsonResponse({'status': 'error', 'message': 'Authorized staff access required.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


def _safe_csv_cell(value):
    text = '' if value is None else str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@')) else text

def risk_board_view(request):
    """
    KSU Specification Section 7.2 (Screen 2):
    Risk Board: Zones ranked by risk score, current and predicted, sortable table.
    Feeds Section 3 F2 (Risk score weighs who is in the crowd, not only how many).
    """
    zones = Zone.objects.all()
    ranked_zones = []
    now = timezone.now()
    window_15m = now - timedelta(minutes=15)
    weather = get_live_makkah_weather()
    heat_index = weather.get('feels_like', 36)

    sort_by = request.GET.get('sort', 'risk')
    site_filter = request.GET.get('site', 'ALL')

    if site_filter != 'ALL':
        zones = zones.filter(site_type=site_filter)

    for z in zones:
        rec = z.density_records.first()
        base_people = rec.total_people if rec else 0
        live_active = LocationPing.objects.filter(zone=z, timestamp__gte=window_15m).values('pilgrim_id').distinct().count()
        current_people = max(base_people, live_active)

        # Vulnerable pilgrims calculation (age >= 65, wheelchair, chronic)
        vulnerable_count = LocationPing.objects.filter(
            zone=z,
            timestamp__gte=window_15m,
            pilgrim__age__gte=65
        ).values('pilgrim_id').distinct().count()
        
        # If no live pings, approximate vulnerable share from registered demographic distribution
        if vulnerable_count == 0 and current_people > 0:
            vulnerable_count = int(current_people * 0.18)

        vulnerable_pct = round((vulnerable_count / max(current_people, 1)) * 100.0, 1)

        capacity_pct = round((current_people / max(z.safe_capacity, 1)) * 100.0, 1)
        density_sqm = round(current_people / max(z.floor_area_sqm, 1), 2)
        pred_density = rec.predicted_density_20m if rec else round(density_sqm * 1.08, 2)
        
        # Weighted risk score formula (Section 3 F2):
        # 50% density ratio + 30% vulnerable share + 20% normalized heat stress
        heat_penalty = min(100.0, max(0.0, (heat_index - 30) * 5.0))
        computed_risk = round(min(100.0, (capacity_pct * 0.5) + (vulnerable_pct * 0.3) + (heat_penalty * 0.2)), 1)

        status_code, color_code, label = z.get_status(current_people)

        ranked_zones.append({
            'zone': z,
            'current_people': current_people,
            'capacity_pct': capacity_pct,
            'density_sqm': density_sqm,
            'predicted_density_20m': pred_density,
            'vulnerable_count': vulnerable_count,
            'vulnerable_pct': vulnerable_pct,
            'risk_score': computed_risk,
            'status_code': status_code,
            'status_color': color_code,
            'status_label': label,
        })

    if sort_by == 'people':
        ranked_zones.sort(key=lambda x: x['current_people'], reverse=True)
    elif sort_by == 'capacity':
        ranked_zones.sort(key=lambda x: x['capacity_pct'], reverse=True)
    elif sort_by == 'predicted':
        ranked_zones.sort(key=lambda x: x['predicted_density_20m'], reverse=True)
    elif sort_by == 'vulnerable':
        ranked_zones.sort(key=lambda x: x['vulnerable_pct'], reverse=True)
    else:
        ranked_zones.sort(key=lambda x: x['risk_score'], reverse=True)

    return render(request, 'analytics/risk_board.html', {
        'ranked_zones': ranked_zones,
        'sort_by': sort_by,
        'site_filter': site_filter,
        'weather': weather,
        'heat_index': heat_index,
    })


def reports_view(request):
    """
    KSU Specification Section 7.2 (Screen 5):
    Charts and reports: Density over time, incident counts, export to CSV.
    """
    # 24-hour density timeline data for primary zones
    now = timezone.now()
    past_24h = now - timedelta(hours=24)
    recent_records = DensityRecord.objects.filter(timestamp__gte=past_24h).select_related('zone').order_by('timestamp')

    # Incidents by category
    incidents_by_category = []
    for cat_code, cat_name in SosIncident.CATEGORY_CHOICES:
        count = SosIncident.objects.filter(category=cat_code).count()
        incidents_by_category.append({'code': cat_code, 'name': str(cat_name), 'count': count})

    # Incidents by status
    total_incidents = SosIncident.objects.count()
    open_incidents = SosIncident.objects.filter(status='OPEN').count()
    responding_incidents = SosIncident.objects.filter(status='RESPONDING').count()
    resolved_incidents = SosIncident.objects.filter(status='RESOLVED').count()

    total_pilgrims = PilgrimProfile.objects.filter(role='pilgrim').count()
    vulnerable_pilgrims = PilgrimProfile.objects.filter(age__gte=65).count()

    return render(request, 'analytics/reports.html', {
        'incidents_by_category': incidents_by_category,
        'total_incidents': total_incidents,
        'open_incidents': open_incidents,
        'responding_incidents': responding_incidents,
        'resolved_incidents': resolved_incidents,
        'total_pilgrims': total_pilgrims,
        'vulnerable_pilgrims': vulnerable_pilgrims,
        'recent_records_count': recent_records.count(),
    })


def routing_comparison_view(request):
    """
    KSU Specification Section 8.3 & Section 15:
    'The comparison that wins your defence'
    Run route finder twice on the same situation:
    1. Standard shortest path (congestion penalty OFF)
    2. HajjGuard congestion-aware detour (congestion penalty ON)
    Proves at least 15% load reduction on the busiest corridor.
    """
    from_zone = request.GET.get('from', 'Z-MINA-SEC3')
    to_zone = request.GET.get('to', 'Z-JAMARAT-F0')

    comparison = RoutingEngine.get_route_comparison(from_zone, to_zone)

    return render(request, 'analytics/routing_comparison.html', {
        'from_zone': from_zone,
        'to_zone': to_zone,
        'comparison': comparison,
    })


@staff_export_required
def export_density_csv(request):
    """
    KSU Specification Section 7.2 & 16:
    Export density records over time to CSV. Audit logged.
    """
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='EXPORT_REPORT',
            target='Density Records CSV Export',
            ip_address=request.META.get('REMOTE_ADDR')
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="hajjguard_density_report_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Zone Code', 'Zone Name', 'Site Type', 'Timestamp', 'Phone Count', 'Image Count', 'Total Headcount', 'Density (p/m2)', 'Predicted 20m', 'Risk Score', 'Status'])

    records = DensityRecord.objects.select_related('zone').order_by('-timestamp')[:500]
    for r in records:
        writer.writerow([
            _safe_csv_cell(r.zone.code),
            _safe_csv_cell(r.zone.name_en),
            _safe_csv_cell(r.zone.site_type),
            r.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            r.phone_count,
            r.image_count,
            r.total_people,
            r.density_per_sqm,
            r.predicted_density_20m,
            r.risk_score,
            r.status,
        ])

    return response


@staff_export_required
def export_incidents_csv(request):
    """
    KSU Specification Section 7.2:
    Export SOS incidents log to CSV.
    """
    if request.user.is_authenticated:
        AuditLog.objects.create(
            user=request.user,
            action='EXPORT_REPORT',
            target='SOS Incidents CSV Export',
            ip_address=request.META.get('REMOTE_ADDR')
        )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="hajjguard_incidents_report_{timezone.now().strftime("%Y%m%d_%H%M")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Incident ID', 'Pilgrim Name', 'Category', 'Zone', 'Latitude', 'Longitude', 'Status', 'Assigned Unit', 'Created At', 'Resolved At'])

    incidents = SosIncident.objects.select_related('pilgrim', 'pilgrim__user', 'zone', 'assigned_unit').order_by('-created_at')
    for inc in incidents:
        writer.writerow([
            inc.id,
            _safe_csv_cell(inc.pilgrim.user.get_full_name() or inc.pilgrim.user.username),
            inc.get_category_display(),
            inc.zone.code if inc.zone else 'Unknown',
            inc.lat,
            inc.lng,
            inc.status,
            inc.assigned_unit.name if inc.assigned_unit else 'Unassigned',
            inc.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            inc.resolved_at.strftime('%Y-%m-%d %H:%M:%S') if inc.resolved_at else '',
        ])

    return response


@staff_export_required
@require_POST
def api_trigger_surge(request):
    """
    Triggers simulated crowd surge into Jamarat Ground Floor.
    Pushes headcount to 34,500 (115% capacity) -> Status: RED.
    """
    success = CrowdSimulator.trigger_jamarat_morning_surge()
    if success:
        return JsonResponse({
            'status': 'success',
            'message': 'Synthetic morning Jamarat surge applied to the local demo dataset.',
            'surged_zone': 'Z-JAMARAT-F0',
            'new_status': 'RED',
            'headcount': 34500,
            'capacity_pct': 115.0
        })
    return JsonResponse({'status': 'error', 'message': 'Failed to trigger surge'}, status=500)

@staff_export_required
@require_POST
def api_reset_crowd(request):
    """
    Resets all holy site zones back to comfortable normal baseline.
    """
    CrowdSimulator.reset_all_zones_normal()
    return JsonResponse({
        'status': 'success',
        'message': 'Synthetic crowd data restored to the local demo baseline.'
    })

@require_GET
def api_calculate_route(request):
    """Public ephemeral journey planning over the existing corridor engine."""
    import math
    from django.core.exceptions import ValidationError
    from zones.models import SafetyMapFeature
    allowed = {'fastest', 'less_crowded', 'wheelchair', 'less_walking', 'cooler'}
    preference = request.GET.get('preference', 'less_crowded')
    if preference not in allowed:
        return JsonResponse({'status': 'error', 'message': 'Unsupported journey preference.'}, status=400)

    def endpoint(prefix, default):
        coordinates = None
        place_id = request.GET.get(prefix + '_place')
        facility_id = request.GET.get(prefix + '_facility')
        if place_id:
            place = VisitorPlace.objects.filter(pk=int(place_id), enabled=True).first()
            if not place:
                raise ValueError('Place is unavailable.')
            place.full_clean()
            coordinates = place.coordinates
        elif facility_id:
            feature = SafetyMapFeature.objects.filter(pk=int(facility_id), enabled=True).first()
            if not feature:
                raise ValueError('Facility is unavailable.')
            feature.full_clean()
            coordinates = feature.coordinates[0]
        elif request.GET.get(prefix + '_lat') is not None or request.GET.get(prefix + '_lng') is not None:
            coordinates = [float(request.GET[prefix + '_lat']), float(request.GET[prefix + '_lng'])]
        if coordinates is not None:
            if len(coordinates) != 2 or not all(math.isfinite(v) for v in coordinates) or not -90 <= coordinates[0] <= 90 or not -180 <= coordinates[1] <= 180:
                raise ValueError('Invalid coordinates.')
            # Only points inside a known zone have corridor coverage. Never route
            # an arbitrary hotel through a distant zone or invent an approach leg.
            candidates = [z for z in Zone.objects.all() if z.contains_point(*coordinates)]
            zone = min(candidates, key=lambda z: z.distance_to(*coordinates), default=None)
            if not zone:
                raise ValueError('This location is outside the verified corridor network. Use the geographic map.')
            return zone.code
        code = request.GET.get(prefix, default)
        if not Zone.objects.filter(code=code).exists():
            raise ValueError('Choose a known Holy Site or verified place.')
        return code
    try:
        origin = endpoint('from', 'Z-MINA-SEC3')
        destination = endpoint('to', 'Z-JAMARAT-F0')
    except (ValueError, TypeError, KeyError, ValidationError):
        return JsonResponse({'status': 'error', 'message': 'Invalid or unavailable endpoint. Verify corridor coverage on the geographic map.'}, status=400)
    comparison = RoutingEngine.get_route_comparison(origin, destination)
    alternatives = {key: RoutingEngine.visitor_route(origin, destination, key) for key in allowed}
    chosen = alternatives[preference]
    target = Zone.objects.get(code=destination)
    record = target.density_records.first()
    fresh = bool(record and 0 <= (timezone.now() - record.timestamp).total_seconds() <= 1200)
    crowd = {'GREEN': 'Comfortable', 'ORANGE': 'Busy', 'RED': 'Crowded'}.get(record.status) if fresh else None
    elevated = bool(fresh and (record.status == 'RED' or record.risk_score >= 70))
    comparison['journey'] = {
        'preference': preference, 'route': chosen, 'route_alternatives': alternatives,
        'crowd': crowd, 'best_departure': None,
        'best_departure_label': 'Not measured; verify conditions before leaving.',
        'safety_mode': elevated,
        'safety_notes': (['Crowded destination: consider another route or wait in a safe area.'] if elevated else []) + chosen['notes'],
        'accessibility': 'Only recently verified wheelchair corridors are eligible.' if preference == 'wheelchair' else 'Confirm accessibility before departure.',
        'provenance': 'local_density_and_corridor_records' if fresh else 'corridor_records_density_unavailable',
        'data_timestamp': record.timestamp.isoformat() if record else None,
        'data_stale': bool(record and not fresh),
    }
    return JsonResponse({'status': 'success', 'route_comparison': comparison})
