from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from .services import RoutingEngine, CrowdSimulator, PredictiveForecaster
from zones.models import Zone

@csrf_exempt
@require_POST
def api_trigger_surge(request):
    """
    Triggers simulated morning crowd surge into Jamarat Ground Floor.
    Pushes headcount to 34,500 (115% capacity) -> Status: RED.
    """
    success = CrowdSimulator.trigger_jamarat_morning_surge()
    if success:
        return JsonResponse({
            'status': 'success',
            'message': 'Morning Jamarat Surge Triggered! Z-JAMARAT-F0 reached 34,500 pilgrims (115% capacity). Status changed to RED.',
            'surged_zone': 'Z-JAMARAT-F0',
            'new_status': 'RED',
            'headcount': 34500,
            'capacity_pct': 115.0
        })
    return JsonResponse({'status': 'error', 'message': 'Failed to trigger surge'}, status=500)

@csrf_exempt
@require_POST
def api_reset_crowd(request):
    """
    Resets all holy site zones back to comfortable normal baseline (GREEN).
    """
    CrowdSimulator.reset_all_zones_normal()
    return JsonResponse({
        'status': 'success',
        'message': 'All holy site zones restored to safe normal capacity (GREEN).'
    })

@require_GET
def api_calculate_route(request):
    """
    Calculates dynamic route between two zones and compares standard shortest path
    versus HajjGuard congestion-aware detour.
    """
    from_zone = request.GET.get('from', 'Z-MINA-SEC3')
    to_zone = request.GET.get('to', 'Z-JAMARAT-F0')

    comparison = RoutingEngine.get_route_comparison(from_zone, to_zone)
    return JsonResponse({
        'status': 'success',
        'route_comparison': comparison
    })

