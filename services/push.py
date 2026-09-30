import logging
import json
from django.conf import settings
from django.utils import timezone
from accounts.models import NotificationEvent, PushSubscription

logger = logging.getLogger(__name__)


def send_notification(event):
    """Deliver a minimum-data Web Push event when VAPID credentials are configured."""
    subscriptions = PushSubscription.objects.filter(user=event.recipient, revoked_at__isnull=True)
    if event.expires_at and event.expires_at <= timezone.now():
        event.delivery_state = 'EXPIRED'
        event.save(update_fields=['delivery_state'])
        return False
    if not subscriptions.exists() or not settings.WEB_PUSH_PRIVATE_KEY or not settings.WEB_PUSH_PUBLIC_KEY:
        return False
    try:
        from pywebpush import webpush
        for subscription in subscriptions:
            webpush(subscription_info={
                'endpoint': subscription.endpoint,
                'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
            }, data=json.dumps(event.payload), vapid_private_key=settings.WEB_PUSH_PRIVATE_KEY,
                    vapid_claims={'sub': settings.WEB_PUSH_CONTACT}, timeout=10)
        event.delivery_state = 'SENT'
        event.delivered_at = timezone.now()
        event.save(update_fields=['delivery_state', 'delivered_at'])
        return True
    except Exception:
        logger.exception('Web Push delivery failed for event %s', event.pk)
        event.delivery_state = 'FAILED'
        event.save(update_fields=['delivery_state'])
        return False
