import json
from urllib.parse import urlsplit
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST
from django.utils import timezone
from .models import PushSubscription, AuditLog


@login_required(login_url='/accounts/login/')
@require_POST
def subscribe_push(request):
    try:
        data = json.loads(request.body or '{}')
        subscription = data['subscription']
        endpoint = subscription['endpoint']
        keys = subscription['keys']
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid push subscription.'}, status=400)
    if len(endpoint) > 2048 or not keys.get('p256dh') or not keys.get('auth'):
        return JsonResponse({'status': 'error', 'message': 'Invalid push subscription.'}, status=400)
    url = urlsplit(endpoint)
    allowed = {'fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com'}
    if url.scheme != 'https' or url.hostname not in allowed or url.port not in (None, 443) or url.username or url.password:
        return JsonResponse({'status': 'error', 'message': 'Unsupported push service endpoint.'}, status=400)
    existing = PushSubscription.objects.filter(endpoint=endpoint).first()
    if existing and existing.user_id != request.user.id:
        return JsonResponse({'status': 'error', 'message': 'Subscription belongs to another account.'}, status=403)
    row, _ = PushSubscription.objects.update_or_create(endpoint=endpoint, defaults={
        'user': request.user, 'p256dh': keys['p256dh'], 'auth': keys['auth'],
        'device_label': str(data.get('device_label', ''))[:120], 'revoked_at': None,
    })
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'PUSH_SUBSCRIBE {row.id}')
    return JsonResponse({'status': 'success', 'id': row.id})


@login_required(login_url='/accounts/login/')
@require_http_methods(['DELETE', 'POST'])
def revoke_push(request, subscription_id):
    row = PushSubscription.objects.filter(id=subscription_id, user=request.user).first()
    if not row:
        return JsonResponse({'status': 'error', 'message': 'Subscription not found.'}, status=404)
    row.revoked_at = timezone.now()
    row.save(update_fields=['revoked_at'])
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'PUSH_REVOKE {row.id}')
    return JsonResponse({'status': 'success'})
