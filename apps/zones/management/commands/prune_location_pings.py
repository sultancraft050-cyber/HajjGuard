from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from zones.models import LocationPing


class Command(BaseCommand):
    help = 'Delete raw location pings older than the configured retention period.'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=float, default=24.0)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        hours = options['hours']
        if hours <= 0:
            raise ValueError('--hours must be positive')
        cutoff = timezone.now() - timedelta(hours=hours)
        qs = LocationPing.objects.filter(timestamp__lt=cutoff)
        count = qs.count()
        if not options['dry_run']:
            with transaction.atomic():
                qs.delete()
        mode = 'would delete' if options['dry_run'] else 'deleted'
        self.stdout.write(f'{mode} {count} location pings older than {hours:g} hours.')
