import json
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import PilgrimGroup, GroupMembership, LocationShareGrant
from accounts.models import PilgrimProfile, AuditLog
from zones.models import Zone, LocationPing
from .services import GroupDriftService

@login_required(login_url='/accounts/login/')
def my_group_view(request):
    """
    KSU Specification Section 7.1 (Screen 6):
    My Group: Member list with last seen zone, group map, drift warnings.
    """
    profile = None
    if request.user.is_authenticated and hasattr(request.user, 'profile'):
        profile = request.user.profile
    else:
        return JsonResponse({'status': 'error', 'message': 'A pilgrim profile is required.'}, status=404)

    membership = GroupMembership.objects.filter(pilgrim=profile, is_active=True).first()
    group = membership.group if membership else None

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
            active_grant = LocationShareGrant.objects.filter(
                pilgrim=m.pilgrim,
                trip__group=group,
                trip__status__in=['PLANNED', 'ACTIVE'],
                trip__starts_at__lte=timezone.now(),
                trip__ends_at__gt=timezone.now(),
                enabled=True,
                consent_given=True,
                revoked_at__isnull=True,
                expires_at__gt=timezone.now(),
            ).first()
            ping_query = LocationPing.objects.filter(pilgrim=m.pilgrim)
            if active_grant and active_grant.consent_timestamp:
                ping_query = ping_query.filter(timestamp__gte=active_grant.consent_timestamp)
            latest_ping = ping_query.order_by('-timestamp').first() if active_grant else None
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
        'is_group_manager': bool(group and (profile.id == group.leader_id or request.user.is_staff)),
    })


staff_lookup_required = user_passes_test(
    lambda user: user.is_authenticated and user.is_staff,
    login_url='/accounts/login/'
)

@staff_lookup_required
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
        # Match only exact opaque QR payloads or exact staff-controlled identifiers.
        pilgrim = PilgrimProfile.objects.filter(
            qr_code_payload__iexact=query
        ).first()
        if not pilgrim:
            from nusuk.models import NusukCard
            card = NusukCard.objects.filter(qr_token=query, is_valid=True).select_related('pilgrim').first()
            pilgrim = card.pilgrim if card else None

        if not pilgrim and query.isdigit():
            pilgrim = PilgrimProfile.objects.filter(user__id=int(query)).first()

        if not pilgrim:
            pilgrim = PilgrimProfile.objects.filter(user__username__iexact=query).first()

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

        if pilgrim is None:
            AuditLog.objects.create(
                user=request.user,
                action='VIEW_PILGRIM',
                target='LOST_LOOKUP_NOT_FOUND',
                ip_address=request.META.get('REMOTE_ADDR'),
            )

    # Recent lookups audit
    recent_audits = AuditLog.objects.filter(action__in=['SCAN_QR', 'VIEW_PILGRIM'], user=request.user)[:5]

    return render(request, 'groups/lost_pilgrim_lookup.html', {
        'query': query,
        'pilgrim': pilgrim,
        'group': group,
        'leader': leader,
        'latest_ping': latest_ping,
        'recent_audits': recent_audits,
    })


@login_required(login_url='/accounts/login/')
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
        code = request.POST.get('code', request.POST.get('group_code', '')).strip().upper()

    if not code:
        return JsonResponse({'status': 'error', 'message': _('Please provide a valid group code.')}, status=400)

    group = PilgrimGroup.objects.filter(join_code=code).first()
    if not group:
        return JsonResponse({'status': 'error', 'message': _('Invalid group code. Group not found.')}, status=404)

    pilgrim = getattr(request.user, 'profile', None)
    if pilgrim is None or pilgrim.role != 'pilgrim':
        return JsonResponse({'status': 'error', 'message': _('A pilgrim account is required.')}, status=403)

    membership, created = GroupMembership.objects.get_or_create(
        group=group,
        pilgrim=pilgrim,
        defaults={'role': 'MEMBER', 'is_active': True}
    )

    return JsonResponse({
        'status': 'success',
        'message': (_('Successfully joined group %(group)s!') if created else _('You are already a member of %(group)s.')) % {'group': group.name},
        'group_id': group.id,
        'group_name': group.name,
        'leader_name': group.leader.user.get_full_name() or group.leader.user.username,
        'leader_phone': group.leader.phone,
    })
