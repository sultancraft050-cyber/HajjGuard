import json
import math
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST, require_http_methods
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import AuditLog, GuardianRelationship, NotificationEvent, PushSubscription
from .models import GeofenceAlert, GroupGeofence, GroupMessage, GroupMembership, LocationShareGrant, PhonePingRequest, PilgrimTrip, PilgrimGroup
from zones.models import LocationPing
from zones.utils import haversine_distance


def _profile(request):
    return getattr(request.user, 'profile', None)


def _trip(profile):
    now = timezone.now()
    return PilgrimTrip.objects.filter(
        pilgrim=profile, status__in=['PLANNED', 'ACTIVE'], starts_at__lte=now, ends_at__gt=now
    ).select_related('group').first()


@login_required(login_url='/accounts/login/')
def pwa_shell(request):
    response = render(request, 'pwa/app.html', {'vapid_public_key': settings.WEB_PUSH_PUBLIC_KEY, 'offline_owner': request.user.pk})
    response['Cache-Control'] = 'no-store'
    return response


def manifest(request):
    return JsonResponse({
        'name': 'HajjGuard Safety', 'short_name': 'HajjGuard', 'start_url': '/app/',
        'display': 'standalone', 'background_color': '#f8fafc', 'theme_color': '#0d5c3a',
        'lang': getattr(request, 'LANGUAGE_CODE', 'ar'),
        'icons': [],
    })


def service_worker(request):
    from django.conf import settings
    return FileResponse(open(settings.BASE_DIR / 'static' / 'pwa' / 'sw.js', 'rb'), content_type='application/javascript')


@login_required(login_url='/accounts/login/')
@require_GET
def current_trip(request):
    profile = _profile(request)
    trip = _trip(profile) if profile else None
    if not trip:
        return JsonResponse({'status': 'no_active_trip'}, status=404)
    grant = LocationShareGrant.objects.filter(trip=trip).first()
    return JsonResponse({'status': 'success', 'trip': {
        'id': trip.id, 'group_id': trip.group_id, 'starts_at': trip.starts_at,
        'ends_at': trip.ends_at, 'status': trip.status,
        'sharing_enabled': bool(grant and grant.is_active),
    }})


@login_required(login_url='/accounts/login/')
@require_GET
def offline_card(request):
    """Owner-only snapshot. Medical fields require a separate explicit choice."""
    import base64
    import io
    import qrcode
    profile = _profile(request)
    if not profile:
        return JsonResponse({'message': 'Profile required.'}, status=404)
    trip = _trip(profile) or PilgrimTrip.objects.filter(pilgrim=profile).select_related('group__leader__user').order_by('-ends_at').first()
    group = trip.group if trip else None
    member = group and GroupMembership.objects.filter(group=group, pilgrim=profile, is_active=True).exists()
    card = getattr(profile, 'nusuk_card', None)
    png = ''
    if card and card.is_valid:
        buf = io.BytesIO()
        qrcode.make(json.dumps({'type': 'HAJJGUARD_SAFETY_CARD', 'version': 1, 'token': card.qr_token})).save(buf, format='PNG')
        png = 'data:image/png;base64,' + base64.b64encode(buf.getvalue()).decode('ascii')
    payload = {
        'owner_id': request.user.pk, 'saved_at': timezone.now(),
        'name': request.user.get_full_name() or request.user.username,
        'group_name': group.name if member else '',
        'leader_phone': group.leader.phone if member else '',
        'leader_name': (group.leader.user.get_full_name() or group.leader.user.username) if member else '',
        'emergency_contact_name': profile.emergency_contact_name,
        'emergency_contact_phone': profile.emergency_contact_phone,
        'trip': {'starts_at': trip.starts_at, 'ends_at': trip.ends_at, 'status': trip.status} if trip else None,
        'qr_image': png, 'medical': None,
    }
    if request.GET.get('include_medical') == 'true':
        payload['medical'] = {'condition': profile.chronic_condition, 'wheelchair': profile.is_wheelchair_user}
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target='OWNER_OFFLINE_CARD')
    response = JsonResponse(payload)
    response['Cache-Control'] = 'no-store, private'
    return response


@login_required(login_url='/accounts/login/')
@require_GET
def sharing_status(request):
    trip = _trip(_profile(request)) if _profile(request) else None
    grant = LocationShareGrant.objects.filter(trip=trip).first() if trip else None
    return JsonResponse({'status': 'success', 'enabled': bool(grant and grant.is_active), 'expires_at': grant.expires_at if grant else None,
                        'consent_version': grant.consent_version if grant else None})


@login_required(login_url='/accounts/login/')
@require_POST
def enable_sharing(request):
    profile = _profile(request)
    trip = _trip(profile) if profile else None
    if not trip:
        return JsonResponse({'status': 'error', 'message': 'No active trip.'}, status=404)
    try:
        data = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    if data.get('consent_given') is not True or not data.get('consent_version'):
        return JsonResponse({'status': 'error', 'message': 'Explicit sharing consent is required.'}, status=400)
    if profile.age < 18 and not GuardianRelationship.objects.filter(dependent=profile, consent_given=True, guardian_approved=True, dependent_approved=True).exists():
        return JsonResponse({'status': 'error', 'message': 'Guardian approval is required.'}, status=403)
    if not GroupMembership.objects.filter(group=trip.group, pilgrim=profile, is_active=True).exists():
        return JsonResponse({'status': 'error', 'message': 'Active group membership required.'}, status=403)
    grant, _ = LocationShareGrant.objects.get_or_create(trip=trip, defaults={'pilgrim': profile, 'expires_at': trip.ends_at})
    grant.pilgrim = profile
    grant.consent_given = True
    grant.consent_version = str(data['consent_version'])[:30]
    grant.consent_timestamp = timezone.now()
    grant.enabled = True
    grant.revoked_at = None
    grant.expires_at = trip.ends_at
    grant.save()
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'LOCATION_SHARING_ENABLED trip={trip.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'enabled': True, 'expires_at': grant.expires_at})


@login_required(login_url='/accounts/login/')
@require_POST
def revoke_sharing(request):
    profile = _profile(request)
    trip = _trip(profile) if profile else None
    grant = LocationShareGrant.objects.filter(trip=trip, pilgrim=profile).first() if trip else None
    if not grant:
        return JsonResponse({'status': 'success', 'enabled': False})
    grant.enabled = False
    grant.revoked_at = timezone.now()
    grant.save(update_fields=['enabled', 'revoked_at'])
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'LOCATION_SHARING_REVOKED trip={trip.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'enabled': False})


def _member_visible(member):
    grant = LocationShareGrant.objects.filter(pilgrim=member.pilgrim, trip__group_id=member.group_id, enabled=True, consent_given=True, revoked_at__isnull=True, expires_at__gt=timezone.now()).first()
    if not grant or not grant.consent_timestamp or not grant.is_active or _trip(member.pilgrim) != grant.trip:
        return None
    ping = LocationPing.objects.filter(pilgrim=member.pilgrim, timestamp__gte=grant.consent_timestamp).order_by('-timestamp').first()
    return {'id': member.pilgrim_id, 'name': member.pilgrim.user.get_full_name() or member.pilgrim.user.username,
            'last_seen': ping.timestamp if ping else None, 'lat': round(ping.lat, 5) if ping else None,
            'lng': round(ping.lng, 5) if ping else None, 'sharing': True}


@login_required(login_url='/accounts/login/')
@require_GET
def live_members(request, group_id):
    profile = _profile(request)
    membership = GroupMembership.objects.filter(group_id=group_id, pilgrim=profile, is_active=True).first()
    if not membership:
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    members = [_member_visible(m) for m in GroupMembership.objects.filter(group_id=group_id, is_active=True).select_related('pilgrim__user')]
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'GROUP_MAP {group_id}')
    return JsonResponse({'status': 'success', 'members': [m for m in members if m]})


def _group_member(request, group_id):
    profile = _profile(request)
    return GroupMembership.objects.filter(group_id=group_id, pilgrim=profile, is_active=True).first() if profile else None


def _group_manager(request, group_id):
    """Return an active member only when the caller is the group leader or staff."""
    membership = _group_member(request, group_id)
    if request.user.is_staff and not membership:
        group = PilgrimGroup.objects.filter(id=group_id).first()
        membership = GroupMembership.objects.filter(group=group, pilgrim_id=group.leader_id, is_active=True).first() if group else None
    if not membership:
        return None
    if request.user.is_staff or membership.pilgrim_id == membership.group.leader_id:
        return membership
    return None


def _json_body(request):
    try:
        value = json.loads(request.body or '{}')
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _message_payload(message, group_id, viewer_id=None):
    payload = {
        'id': message.id,
        'sender': message.sender.user.get_full_name() or message.sender.user.username,
        'text': message.text,
        'image_url': f'/groups/api/groups/{group_id}/messages/{message.id}/attachment/' if message.image else None,
        'is_announcement': message.is_announcement,
        'created_at': message.created_at.isoformat(),
    }
    if viewer_id is not None:
        payload['can_delete'] = message.sender_id == viewer_id
    return payload


@login_required(login_url='/accounts/login/')
@require_GET
def group_management(request, group_id):
    manager = _group_manager(request, group_id)
    if not manager:
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    group = manager.group
    now = timezone.now()
    rows = GroupMembership.objects.filter(group=group, is_active=True).select_related('pilgrim__user')
    members = []
    for row in rows:
        active_trip = PilgrimTrip.objects.filter(
            pilgrim=row.pilgrim, group=group, status__in=['PLANNED', 'ACTIVE'],
            starts_at__lte=now, ends_at__gt=now,
        ).first()
        grant = LocationShareGrant.objects.filter(pilgrim=row.pilgrim, trip=active_trip).first() if active_trip else None
        ping_query = LocationPing.objects.filter(pilgrim=row.pilgrim)
        if grant and grant.consent_timestamp:
            ping_query = ping_query.filter(timestamp__gte=grant.consent_timestamp)
        last_ping = ping_query.order_by('-timestamp').first() if grant and grant.is_active else None
        members.append({
            'id': row.pilgrim_id,
            'name': row.pilgrim.user.get_full_name() or row.pilgrim.user.username,
            'role': row.role,
            'is_leader': row.pilgrim_id == group.leader_id,
            'sharing': bool(grant and grant.is_active),
            'freshness': ('current' if last_ping and (now - last_ping.timestamp).total_seconds() <= 120 else 'stale') if grant and grant.is_active else 'not_shared',
            'last_seen': last_ping.timestamp.isoformat() if last_ping else None,
        })
    fences = list(GroupGeofence.objects.filter(group=group, trip__ends_at__gt=now).values(
        'id', 'trip_id', 'name', 'center_lat', 'center_lng', 'radius_meters', 'enabled'
    ))
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'GROUP_VIEW {group.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'group': {'id': group.id, 'name': group.name, 'join_code': group.join_code}, 'members': members, 'geofences': fences})


@login_required(login_url='/accounts/login/')
@require_GET
def messages(request, group_id):
    if not _group_member(request, group_id):
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    try:
        after_id = max(0, int(request.GET.get('after_id', 0)))
        limit = min(100, max(1, int(request.GET.get('limit', 50))))
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid message cursor.'}, status=400)
    query = GroupMessage.objects.filter(group_id=group_id, deleted_at__isnull=True).select_related('sender__user')
    if after_id:
        query = query.filter(id__gt=after_id)
    rows = query.order_by('id')[:limit]
    return JsonResponse({'status': 'success', 'messages': [_message_payload(m, group_id, _profile(request).id) for m in rows]})


@login_required(login_url='/accounts/login/')
@require_POST
def create_message(request, group_id):
    membership = _group_member(request, group_id)
    if not membership:
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    text = str(data.get('text', '')).strip()
    if not text or len(text) > 2000:
        return JsonResponse({'status': 'error', 'message': 'Message must contain 1-2000 characters.'}, status=400)
    recent = GroupMessage.objects.filter(sender=membership.pilgrim, created_at__gte=timezone.now() - timedelta(seconds=3)).exists()
    if recent:
        return JsonResponse({'status': 'error', 'message': 'Please wait before sending another message.'}, status=429)
    message = GroupMessage.objects.create(group_id=group_id, sender=membership.pilgrim, text=text)
    payload = _message_payload(message, group_id, membership.pilgrim_id)
    async_to_sync(get_channel_layer().group_send)(f'group-{group_id}', {'type': 'group_event', 'payload': {'type': 'chat.message', 'message': payload}})
    AuditLog.objects.create(user=request.user, action='GROUP_CHAT', target=f'MESSAGE_CREATE {message.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'message': payload})


@login_required(login_url='/accounts/login/')
@require_POST
def create_announcement(request, group_id):
    manager = _group_manager(request, group_id)
    if not manager:
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    data = _json_body(request)
    text = str(data.get('text', '')).strip() if data else ''
    if not text or len(text) > 2000:
        return JsonResponse({'message': 'Announcement must contain 1-2000 characters.'}, status=400)
    if GroupMessage.objects.filter(group_id=group_id, is_announcement=True, created_at__gte=timezone.now() - timedelta(seconds=10)).exists():
        return JsonResponse({'message': 'Please wait before sending another announcement.'}, status=429)
    message = GroupMessage.objects.create(group_id=group_id, sender=manager.pilgrim, text=text, is_announcement=True)
    payload = _message_payload(message, group_id, manager.pilgrim_id)
    async_to_sync(get_channel_layer().group_send)(f'group-{group_id}', {'type': 'group_event', 'payload': {'type': 'chat.announcement', 'message': payload}})
    from services.push import send_notification
    for member in GroupMembership.objects.filter(group_id=group_id, is_active=True).exclude(pilgrim=manager.pilgrim).select_related('pilgrim__user'):
        event = NotificationEvent.objects.create(recipient=member.pilgrim.user, event_type='CHAT', payload={'title': 'Group announcement', 'body': text[:160], 'data': {'group_id': group_id, 'message_id': message.id}}, expires_at=timezone.now() + timedelta(hours=24))
        send_notification(event)
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'ANNOUNCEMENT_CREATE {message.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'message': payload})


@login_required(login_url='/accounts/login/')
@require_POST
def remove_member(request, group_id, member_id):
    manager = _group_manager(request, group_id)
    if not manager:
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    target = GroupMembership.objects.filter(group_id=group_id, pilgrim_id=member_id, is_active=True).first()
    if not target or target.pilgrim_id == manager.group.leader_id:
        return JsonResponse({'message': 'The group leader cannot be removed.'}, status=400)
    target.is_active = False
    target.save(update_fields=['is_active'])
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'MEMBER_REMOVE {member_id} GROUP {group_id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'member_id': member_id})


@login_required(login_url='/accounts/login/')
@require_http_methods(['PATCH'])
def update_member_role(request, group_id, member_id):
    manager = _group_manager(request, group_id)
    if not manager:
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    target = GroupMembership.objects.filter(group_id=group_id, pilgrim_id=member_id, is_active=True).first()
    data = _json_body(request)
    role = data.get('role') if data else None
    valid_roles = {value for value, _ in GroupMembership.ROLE_CHOICES}
    if not target or target.pilgrim_id == manager.group.leader_id or role not in valid_roles:
        return JsonResponse({'message': 'Invalid member role change.'}, status=400)
    target.role = role
    target.save(update_fields=['role'])
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'MEMBER_ROLE {member_id}={role} GROUP {group_id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'member_id': member_id, 'role': role})


@login_required(login_url='/accounts/login/')
@require_POST
def rotate_join_code(request, group_id):
    manager = _group_manager(request, group_id)
    if not manager:
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    if AuditLog.objects.filter(
        user=request.user,
        action='GROUP_MANAGEMENT',
        target__startswith=f'JOIN_CODE_ROTATE GROUP {group_id}',
        timestamp__gte=timezone.now() - timedelta(minutes=1),
    ).exists():
        return JsonResponse({'message': 'Please wait before rotating the group code.'}, status=429)
    manager.group.join_code = manager.group.generate_join_code()
    manager.group.save(update_fields=['join_code'])
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'JOIN_CODE_ROTATE GROUP {group_id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'join_code': manager.group.join_code})


@login_required(login_url='/accounts/login/')
@require_GET
def list_geofences(request, group_id):
    if not _group_member(request, group_id):
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    rows = GroupGeofence.objects.filter(group_id=group_id, enabled=True, trip__ends_at__gt=timezone.now(), trip__status__in=['PLANNED', 'ACTIVE'])
    return JsonResponse({'status': 'success', 'geofences': [{'id': g.id, 'name': g.name, 'lat': g.center_lat, 'lng': g.center_lng, 'radius_meters': g.radius_meters} for g in rows]})


@login_required(login_url='/accounts/login/')
@require_POST
def create_geofence(request, group_id):
    membership = _group_member(request, group_id)
    if not membership or (membership.pilgrim_id != membership.group.leader_id and not request.user.is_staff):
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    try:
        data = json.loads(request.body or '{}')
        name, lat, lng = str(data['name']).strip(), float(data['lat']), float(data['lng'])
        radius = int(data.get('radius_meters', 100))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'message': 'Invalid geofence.'}, status=400)
    if not name or not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180 or not 20 <= radius <= 5000:
        return JsonResponse({'message': 'Invalid geofence.'}, status=400)
    trip = PilgrimTrip.objects.filter(group_id=group_id, status__in=['PLANNED', 'ACTIVE'], ends_at__gt=timezone.now()).first()
    if not trip:
        return JsonResponse({'message': 'No active group trip.'}, status=409)
    fence = GroupGeofence.objects.create(group_id=group_id, trip=trip, name=name, center_lat=lat, center_lng=lng, radius_meters=radius)
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'GEOFENCE_CREATE {fence.id}')
    return JsonResponse({'status': 'success', 'id': fence.id})


@login_required(login_url='/accounts/login/')
@require_http_methods(['PATCH'])
def update_geofence(request, geofence_id):
    fence = GroupGeofence.objects.filter(id=geofence_id).select_related('group').first()
    if not fence:
        return JsonResponse({'message': 'Meeting point not found.'}, status=404)
    manager = _group_manager(request, fence.group_id)
    if not manager:
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    data = _json_body(request)
    if data is None:
        return JsonResponse({'message': 'Invalid JSON.'}, status=400)
    try:
        name = str(data.get('name', fence.name)).strip()
        lat = float(data.get('lat', fence.center_lat))
        lng = float(data.get('lng', fence.center_lng))
        radius = int(data.get('radius_meters', fence.radius_meters))
        enabled = bool(data.get('enabled', fence.enabled))
    except (TypeError, ValueError):
        return JsonResponse({'message': 'Invalid meeting point.'}, status=400)
    if not name or not math.isfinite(lat) or not math.isfinite(lng) or not -90 <= lat <= 90 or not -180 <= lng <= 180 or not 20 <= radius <= 5000:
        return JsonResponse({'message': 'Invalid meeting point.'}, status=400)
    fence.name, fence.center_lat, fence.center_lng = name, lat, lng
    fence.radius_meters, fence.enabled = radius, enabled
    fence.save(update_fields=['name', 'center_lat', 'center_lng', 'radius_meters', 'enabled'])
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'GEOFENCE_UPDATE {fence.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'id': fence.id, 'enabled': fence.enabled})


@login_required(login_url='/accounts/login/')
@require_http_methods(['DELETE'])
def delete_geofence(request, geofence_id):
    fence = GroupGeofence.objects.filter(id=geofence_id).select_related('group').first()
    if not fence:
        return JsonResponse({'message': 'Meeting point not found.'}, status=404)
    if not _group_manager(request, fence.group_id):
        return JsonResponse({'message': 'Group leader or staff access required.'}, status=403)
    fence.enabled = False
    fence.save(update_fields=['enabled'])
    AuditLog.objects.create(user=request.user, action='GROUP_MANAGEMENT', target=f'GEOFENCE_DISABLE {fence.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'id': fence.id, 'enabled': False})


@login_required(login_url='/accounts/login/')
@require_POST
def phone_ping(request, group_id, member_id):
    membership = _group_member(request, group_id)
    target_membership = GroupMembership.objects.filter(group_id=group_id, pilgrim_id=member_id, is_active=True).first()
    if not membership or not target_membership:
        return JsonResponse({'status': 'error', 'message': 'Active group membership required.'}, status=403)
    if target_membership.pilgrim_id == membership.pilgrim_id:
        return JsonResponse({'status': 'error', 'message': 'Choose another member.'}, status=400)
    if PhonePingRequest.objects.filter(requester=membership.pilgrim, created_at__gte=timezone.now() - timedelta(minutes=1)).exists():
        return JsonResponse({'status': 'error', 'message': 'Ping rate limit exceeded.'}, status=429)
    target_trip = _trip(target_membership.pilgrim)
    if not target_trip or not PushSubscription.objects.filter(user=target_membership.pilgrim.user, revoked_at__isnull=True).exists():
        return JsonResponse({'status': 'error', 'message': 'Target has no active device subscription.'}, status=409)
    ping = PhonePingRequest.objects.create(requester=membership.pilgrim, target=target_membership.pilgrim, group_id=group_id, reason='Group member requested a check-in', expires_at=timezone.now() + timedelta(minutes=2))
    event = NotificationEvent.objects.create(recipient=target_membership.pilgrim.user, event_type='PHONE_PING', payload={'request_id': ping.id, 'message': 'A group member requested a check-in.'}, expires_at=ping.expires_at)
    from services.push import send_notification
    event.payload = {'title': 'HajjGuard check-in', 'body': 'A group member requested a check-in.', 'data': {'request_id': ping.id}}
    event.save(update_fields=['payload'])
    send_notification(event)
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'PHONE_PING {target_membership.pilgrim_id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'success', 'request_id': ping.id, 'notification_id': event.id})


@login_required(login_url='/accounts/login/')
@require_POST
def acknowledge_geofence(request, geofence_id):
    from .models import GeofenceAlert
    alert = GeofenceAlert.objects.filter(geofence_id=geofence_id, pilgrim=_profile(request), acknowledged_at__isnull=True).order_by('-occurred_at').first()
    if not alert:
        return JsonResponse({'status': 'error', 'message': 'Alert not found.'}, status=404)
    alert.acknowledged_at = timezone.now()
    alert.save(update_fields=['acknowledged_at'])
    return JsonResponse({'status': 'success'})


@login_required(login_url='/accounts/login/')
@require_GET
def my_geofence_alerts(request):
    """Return the current pilgrim's own unacknowledged safety alerts only."""
    profile = _profile(request)
    now = timezone.now()
    trip = _trip(profile) if profile else None
    grant = LocationShareGrant.objects.filter(trip=trip, pilgrim=profile).first() if trip else None
    alerts = []
    if not grant or not grant.is_active:
        return JsonResponse({'status': 'success', 'alerts': [], 'sharing': False})
    rows = GeofenceAlert.objects.filter(pilgrim=profile, acknowledged_at__isnull=True, occurred_at__gte=now-timedelta(hours=24)).select_related('geofence').order_by('-occurred_at')[:10]
    alerts.extend([{
        'id': row.id, 'geofence_id': row.geofence_id, 'name': row.geofence.name,
        'event_type': row.event_type, 'occurred_at': row.occurred_at,
        'freshness': 'current' if (now-row.occurred_at).total_seconds() <= 120 else 'stale',
        'reason': f"{'You left' if row.event_type == 'EXIT' else 'You entered'} the meeting area: {row.geofence.name}.",
        'evidence': 'Validated device locations crossed the configured meeting-area radius.',
        'action': 'Return to the agreed meeting point or contact your leader.',
    } for row in rows])
    remaining = (grant.expires_at-now).total_seconds()
    if remaining <= 1800:
        alerts.append({'event_type': 'SHARING_EXPIRY', 'reason': 'Location sharing expires within 30 minutes.', 'evidence': 'Your consent expiry timestamp.', 'occurred_at': now, 'freshness': 'current'})
    own = LocationPing.objects.filter(pilgrim=profile).order_by('-timestamp').first()
    leader_grant = LocationShareGrant.objects.filter(pilgrim=trip.group.leader, trip__group=trip.group, trip__starts_at__lte=now, trip__ends_at__gt=now, trip__status__in=['PLANNED','ACTIVE']).first()
    leader = LocationPing.objects.filter(pilgrim=trip.group.leader).order_by('-timestamp').first() if leader_grant and leader_grant.is_active else None
    if own and leader and profile.pk != trip.group.leader_id:
        fresh = all((now-p.timestamp).total_seconds() <= 120 for p in (own, leader))
        uncertainty = max(own.accuracy_meters or 0, leader.accuracy_meters or 0)
        distance = haversine_distance(own.lat, own.lng, leader.lat, leader.lng)
        if not fresh:
            alerts.append({'event_type':'STALE', 'reason':'Location is stale; group separation cannot be confirmed.', 'evidence':'One or both locations are older than two minutes.', 'freshness':'stale', 'occurred_at':own.timestamp})
        elif distance > 50 + uncertainty:
            alerts.append({'event_type':'DRIFT', 'reason':'You are separating from your group leader.', 'evidence':f'Fresh consented device fixes are {round(distance)} m apart; accuracy allowance {round(uncertainty)} m.', 'freshness':'current', 'occurred_at':own.timestamp, 'action':'Return to your meeting point or contact your leader.'})
    for alert in alerts:
        alert['disable'] = 'Stop location sharing in the safety app to stop new location alerts.'
    return JsonResponse({'status': 'success', 'alerts': alerts, 'sharing': True})


@login_required(login_url='/accounts/login/')
@require_POST
def upload_attachment(request, group_id, message_id):
    import io
    import uuid
    from PIL import Image, UnidentifiedImageError
    from django.core.files.base import ContentFile
    membership = _group_member(request, group_id)
    row = GroupMessage.objects.filter(id=message_id, group_id=group_id, sender=_profile(request), deleted_at__isnull=True).first()
    if not membership or row is None:
        return JsonResponse({'message': 'Message access denied.'}, status=403)
    upload = request.FILES.get('image')
    if not upload or upload.size > 5 * 1024 * 1024 or upload.content_type not in {'image/png', 'image/jpeg', 'image/webp'}:
        return JsonResponse({'message': 'A PNG, JPEG or WebP image up to 5 MB is required.'}, status=400)
    try:
        with Image.open(upload) as image:
            if image.format not in {'PNG', 'JPEG', 'WEBP'} or image.width * image.height > 16000000:
                raise ValueError('Unsupported image')
            image.load()
            cleaned = image.convert('RGB')
            buffer = io.BytesIO()
            cleaned.save(buffer, format='JPEG', quality=85)
        from django.core.files.storage import FileSystemStorage
        row.image.storage = FileSystemStorage(location=settings.BASE_DIR / 'private_uploads')
        if row.image:
            row.image.delete(save=False)
        row.image.save(f'{uuid.uuid4().hex}.jpg', ContentFile(buffer.getvalue()))
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return JsonResponse({'message': 'Invalid image.'}, status=400)
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'CHAT_ATTACHMENT {row.id}')
    return JsonResponse({'status': 'success', 'image_url': f'/api/groups/{group_id}/messages/{row.id}/attachment/'})


@login_required(login_url='/accounts/login/')
@require_GET
def attachment(request, group_id, message_id):
    from django.core.files.storage import FileSystemStorage
    if not _group_member(request, group_id):
        return JsonResponse({'message': 'Group membership required.'}, status=403)
    row = GroupMessage.objects.filter(id=message_id, group_id=group_id, deleted_at__isnull=True).first()
    if not row or not row.image:
        return JsonResponse({'message': 'Image not found.'}, status=404)
    storage = FileSystemStorage(location=settings.BASE_DIR / 'private_uploads')
    response = FileResponse(storage.open(row.image.name, 'rb'), content_type='image/jpeg')
    response['Cache-Control'] = 'no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@login_required(login_url='/accounts/login/')
@require_POST
def moderate_message(request, group_id, message_id):
    if not _group_member(request, group_id) and not request.user.is_staff:
        return JsonResponse({'message': 'Group access denied.'}, status=403)
    row = GroupMessage.objects.filter(id=message_id, group_id=group_id).first()
    if row is None:
        return JsonResponse({'message': 'Message not found.'}, status=404)
    data = json.loads(request.body or '{}')
    if data.get('action') == 'report':
        row.reported = True
    elif data.get('action') == 'delete' and (request.user.is_staff or row.sender == _profile(request)):
        row.deleted_at = timezone.now()
    else:
        return JsonResponse({'message': 'Moderation access denied.'}, status=403)
    row.save(update_fields=['reported', 'deleted_at'])
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'CHAT_MODERATION {row.id}')
    return JsonResponse({'status': 'success'})


def evaluate_geofences(pilgrim, lat, lng):
    """Create cooldown-protected enter/exit alerts for a validated telemetry ping."""
    from .models import GeofenceAlert
    from accounts.models import NotificationEvent
    from services.push import send_notification
    now = timezone.now()
    trip = _trip(pilgrim)
    grant = LocationShareGrant.objects.filter(trip=trip, pilgrim=pilgrim).first() if trip else None
    if not grant or not grant.is_active:
        return
    memberships = GroupMembership.objects.filter(pilgrim=pilgrim, is_active=True).select_related('group')
    for membership in memberships:
        for fence in GroupGeofence.objects.filter(group=membership.group, enabled=True, trip__status__in=['PLANNED', 'ACTIVE'], trip__ends_at__gt=now):
            inside = haversine_distance(fence.center_lat, fence.center_lng, lat, lng) <= fence.radius_meters
            recent_pings = list(LocationPing.objects.filter(pilgrim=pilgrim).order_by('-timestamp')[:2])
            previous = recent_pings[1] if len(recent_pings) > 1 else None
            if previous is None:
                continue
            if (now-previous.timestamp).total_seconds() > 120:
                continue
            was_inside = haversine_distance(fence.center_lat, fence.center_lng, previous.lat, previous.lng) <= fence.radius_meters
            event_type = 'ENTER' if inside and not was_inside else ('EXIT' if was_inside and not inside else None)
            if not event_type:
                continue
            recent = GeofenceAlert.objects.filter(pilgrim=pilgrim, geofence=fence, event_type=event_type, occurred_at__gte=now - timedelta(seconds=fence.cooldown_seconds)).exists()
            if recent:
                continue
            alert = GeofenceAlert.objects.create(pilgrim=pilgrim, geofence=fence, event_type=event_type)
            AuditLog.objects.create(user=pilgrim.user, action='GEOFENCE_ALERT', target=f'Alert {alert.pk} {event_type}')
            event = NotificationEvent.objects.create(recipient=pilgrim.user, event_type='GEOFENCE', payload={'title': 'HajjGuard meeting-area alert', 'body': f'You {"left" if event_type == "EXIT" else "entered"} a meeting area. Open the safety app for timestamp, reason and sharing controls.', 'data': {'alert_id': alert.id}})
            send_notification(event)
