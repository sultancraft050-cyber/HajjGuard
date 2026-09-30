import json
import math
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from accounts.models import AuditLog, GuardianRelationship, NotificationEvent, PushSubscription
from .models import GroupGeofence, GroupMessage, GroupMembership, LocationShareGrant, PhonePingRequest, PilgrimTrip
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
    return render(request, 'pwa/app.html', {'vapid_public_key': settings.WEB_PUSH_PUBLIC_KEY})


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


@login_required(login_url='/accounts/login/')
@require_GET
def messages(request, group_id):
    if not _group_member(request, group_id):
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    rows = GroupMessage.objects.filter(group_id=group_id, deleted_at__isnull=True).select_related('sender__user').order_by('-created_at')[:100]
    return JsonResponse({'status': 'success', 'messages': [{'id': m.id, 'sender': m.sender.user.get_full_name() or m.sender.user.username,
        'text': m.text, 'image_url': f'/api/groups/{group_id}/messages/{m.id}/attachment/' if m.image else None, 'created_at': m.created_at} for m in reversed(list(rows))]})


@login_required(login_url='/accounts/login/')
@require_POST
def create_message(request, group_id):
    membership = _group_member(request, group_id)
    if not membership:
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    try:
        data = json.loads(request.body or '{}')
    except (TypeError, ValueError):
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON.'}, status=400)
    text = str(data.get('text', '')).strip()
    if not text or len(text) > 2000:
        return JsonResponse({'status': 'error', 'message': 'Message must contain 1-2000 characters.'}, status=400)
    recent = GroupMessage.objects.filter(sender=membership.pilgrim, created_at__gte=timezone.now() - timedelta(seconds=3)).exists()
    if recent:
        return JsonResponse({'status': 'error', 'message': 'Please wait before sending another message.'}, status=429)
    message = GroupMessage.objects.create(group_id=group_id, sender=membership.pilgrim, text=text)
    async_to_sync(get_channel_layer().group_send)(f'group-{group_id}', {'type': 'group_event', 'payload': {'type': 'chat.message', 'message': {'id': message.id, 'sender': membership.pilgrim.user.get_full_name() or membership.pilgrim.user.username, 'text': message.text, 'created_at': message.created_at.isoformat()}}})
    return JsonResponse({'status': 'success', 'message': {'id': message.id, 'text': message.text, 'created_at': message.created_at}})


@login_required(login_url='/accounts/login/')
@require_GET
def list_geofences(request, group_id):
    if not _group_member(request, group_id):
        return JsonResponse({'status': 'error', 'message': 'Group membership required.'}, status=403)
    rows = GroupGeofence.objects.filter(group_id=group_id, enabled=True)
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
    memberships = GroupMembership.objects.filter(pilgrim=pilgrim, is_active=True).select_related('group')
    for membership in memberships:
        for fence in GroupGeofence.objects.filter(group=membership.group, enabled=True, trip__pilgrim=pilgrim, trip__status__in=['PLANNED', 'ACTIVE'], trip__ends_at__gt=now):
            inside = haversine_distance(fence.center_lat, fence.center_lng, lat, lng) <= fence.radius_meters
            recent_pings = list(LocationPing.objects.filter(pilgrim=pilgrim).order_by('-timestamp')[:2])
            previous = recent_pings[1] if len(recent_pings) > 1 else None
            if previous is None:
                continue
            was_inside = haversine_distance(fence.center_lat, fence.center_lng, previous.lat, previous.lng) <= fence.radius_meters
            event_type = 'ENTER' if inside and not was_inside else ('EXIT' if was_inside and not inside else None)
            if not event_type:
                continue
            recent = GeofenceAlert.objects.filter(pilgrim=pilgrim, geofence=fence, event_type=event_type, occurred_at__gte=now - timedelta(seconds=fence.cooldown_seconds)).exists()
            if recent:
                continue
            alert = GeofenceAlert.objects.create(pilgrim=pilgrim, geofence=fence, event_type=event_type)
            event = NotificationEvent.objects.create(recipient=pilgrim.user, event_type='GEOFENCE', payload={'title': fence.name, 'body': f'Geofence {event_type.lower()} alert.', 'data': {'alert_id': alert.id}})
            send_notification(event)
