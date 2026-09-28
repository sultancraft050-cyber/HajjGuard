import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import PilgrimGroup, GroupMembership
from accounts.models import PilgrimProfile, AuditLog
from zones.models import Zone, LocationPing
from .services import GroupDriftService

def my_group_view(request):
    """
    KSU Specification Section 7.1 (Screen 6):
    My Group: Member list with last seen zone, group map, drift warnings.
    """
    profile = None
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
    else:
        # Default pilgrim profile for demonstration
        profile = PilgrimProfile.objects.filter(role='pilgrim').first()

    membership = GroupMembership.objects.filter(pilgrim=profile, is_active=True).first()
    group = membership.group if membership else PilgrimGroup.objects.first()

    members_data = []
    group_centroid = None
    drift_alert = None

    if group:
        # Compute real-time drift metrics using GroupDriftService
        metrics = GroupDriftService.compute_group_metrics(group.id)
        if metrics:
            group_centroid = {
                'lat': metrics['centroid_lat'],
                'lng': metrics['centroid_lng'],
                'dispersion_m': metrics['dispersion_radius_meters'],
            }
            if metrics.get('drift_alert'):
                drift_alert = metrics['drift_alert']

        for m in group.members.filter(is_active=True).select_related('pilgrim', 'pilgrim__user'):
            latest_ping = LocationPing.objects.filter(pilgrim=m.pilgrim).order_by('-timestamp').first()
            p_dist = 0.0
            if group_centroid and latest_ping:
                from zones.utils import haversine_distance
                p_dist = round(haversine_distance(group_centroid['lat'], group_centroid['lng'], latest_ping.lat, latest_ping.lng), 1)

            members_data.append({
                'membership': m,
                'pilgrim': m.pilgrim,
                'role': m.get_role_display(),
                'latest_ping': latest_ping,
                'distance_from_centroid': p_dist,
                'is_drifting': p_dist > 50.0,
            })

    return render(request, 'groups/my_group.html', {
        'profile': profile,
        'group': group,
        'members_data': members_data,
        'group_centroid': group_centroid,
        'drift_alert': drift_alert,
    })


def lost_pilgrim_lookup_view(request):
    """
    KSU Specification Section 7.2 (Screen 4) & Section 16 (PDPL):
    Lost Pilgrim Lookup: Scan a QR code or type an ID, shows group and leader contact.
    Every lookup is automatically recorded in AuditLog table.
    """
    query = request.GET.get('q', '').strip()
    pilgrim = None
    group = None
    leader = None
    latest_ping = None

    if query:
        # Match by QR payload, user ID, username, phone, or national identity
        pilgrim = PilgrimProfile.objects.filter(
            qr_code_payload__iexact=query
        ).first()

        if not pilgrim and query.isdigit():
            pilgrim = PilgrimProfile.objects.filter(user__id=int(query)).first()

        if not pilgrim:
            pilgrim = PilgrimProfile.objects.filter(phone__icontains=query).first() or \
                      PilgrimProfile.objects.filter(user__username__icontains=query).first() or \
                      PilgrimProfile.objects.filter(user__first_name__icontains=query).first()

        if pilgrim:
            # Audit log entry as mandated by KSU specification Section 16
            current_user = request.user if request.user.is_authenticated else None
            AuditLog.objects.create(
                user=current_user,
                action='SCAN_QR' if 'HAJJGUARD' in query.upper() or 'PRM' in query.upper() else 'VIEW_PILGRIM',
                target=f"Pilgrim #{pilgrim.id} ({pilgrim.user.get_full_name() or pilgrim.user.username})",
                ip_address=request.META.get('REMOTE_ADDR')
            )

            membership = GroupMembership.objects.filter(pilgrim=pilgrim, is_active=True).first()
            if membership:
                group = membership.group
                leader = group.leader

            latest_ping = LocationPing.objects.filter(pilgrim=pilgrim).order_by('-timestamp').first()

    # Recent lookups audit
    recent_audits = AuditLog.objects.filter(action__in=['SCAN_QR', 'VIEW_PILGRIM'])[:5]

    return render(request, 'groups/lost_pilgrim_lookup.html', {
        'query': query,
        'pilgrim': pilgrim,
        'group': group,
        'leader': leader,
        'latest_ping': latest_ping,
        'recent_audits': recent_audits,
    })


@csrf_exempt
@require_POST
def api_join_group(request):
    """
    KSU Specification Section 2.1:
    Join a Hajj group with a code without requiring an admin.
    """
    try:
        data = json.loads(request.body)
        code = data.get('code', '').strip().upper()
    except Exception:
        code = request.POST.get('code', '').strip().upper()

    if not code:
        return JsonResponse({'status': 'error', 'message': _('Please provide a valid group code.')}, status=400)

    group = PilgrimGroup.objects.filter(join_code=code).first()
    if not group:
        return JsonResponse({'status': 'error', 'message': _('Invalid group code. Group not found.')}, status=404)

    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        pilgrim = request.user.profile
    else:
        pilgrim = PilgrimProfile.objects.filter(role='pilgrim').first()

    membership, created = GroupMembership.objects.get_or_create(
        group=group,
        pilgrim=pilgrim,
        defaults={'role': 'MEMBER', 'is_active': True}
    )

    return JsonResponse({
        'status': 'success',
        'message': _('Successfully joined group %(group)s!') % {'group': group.name},
        'group_id': group.id,
        'group_name': group.name,
        'leader_name': group.leader.user.get_full_name() or group.leader.user.username,
        'leader_phone': group.leader.phone,
    })
