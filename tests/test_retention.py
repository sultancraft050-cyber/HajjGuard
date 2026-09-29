from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone

from accounts.models import PilgrimProfile
from zones.models import LocationPing


class LocationRetentionTests(TestCase):
    def test_dry_run_does_not_delete_and_delete_respects_boundary(self):
        profile = PilgrimProfile.objects.create(user=User.objects.create_user('retention'))
        now = timezone.now()
        LocationPing.objects.create(pilgrim=profile, lat=21.4, lng=39.8, timestamp=now - timedelta(hours=25))
        LocationPing.objects.create(pilgrim=profile, lat=21.4, lng=39.8, timestamp=now - timedelta(hours=1))
        call_command('prune_location_pings', hours=24, dry_run=True)
        self.assertEqual(LocationPing.objects.count(), 2)
        call_command('prune_location_pings', hours=24)
        self.assertEqual(LocationPing.objects.count(), 1)
