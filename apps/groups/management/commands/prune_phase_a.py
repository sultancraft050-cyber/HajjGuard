from django.core.management.base import BaseCommand
from django.utils import timezone
from groups.models import GroupMessage, GeofenceAlert, PilgrimTrip
from accounts.models import NotificationEvent


class Command(BaseCommand):
    help = 'Delete Phase A messages, attachments, notifications, and alerts after trip expiry.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        now = timezone.now()
        expired_trips = PilgrimTrip.objects.filter(ends_at__lte=now)
        if not options['dry_run']:
            expired_trips.filter(status__in=['PLANNED', 'ACTIVE']).update(status='ENDED')
        messages = GroupMessage.objects.filter(group__trips__in=expired_trips)
        notifications = NotificationEvent.objects.filter(expires_at__isnull=False, expires_at__lte=now)
        alerts = GeofenceAlert.objects.filter(occurred_at__lte=now - timezone.timedelta(days=30))
        if options['dry_run']:
            self.stdout.write(f'Would delete {messages.count()} messages, {notifications.count()} notifications, {alerts.count()} alerts.')
            return
        for message in messages.iterator():
            if message.image:
                message.image.delete(save=False)
        deleted_messages, _ = messages.delete()
        deleted_notifications, _ = notifications.delete()
        deleted_alerts, _ = alerts.delete()
        self.stdout.write(self.style.SUCCESS(f'Deleted {deleted_messages} messages, {deleted_notifications} notifications, {deleted_alerts} alerts.'))
