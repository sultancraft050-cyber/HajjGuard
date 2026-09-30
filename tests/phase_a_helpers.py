from datetime import timedelta
from django.utils import timezone
from groups.models import PilgrimGroup, GroupMembership, PilgrimTrip, LocationShareGrant


def consented_trip(profile):
    campaign = profile.nusuk_card.campaign
    group = PilgrimGroup.objects.create(name='Telemetry consent fixture', campaign=campaign, leader=profile)
    GroupMembership.objects.create(group=group, pilgrim=profile)
    now = timezone.now()
    trip = PilgrimTrip.objects.create(pilgrim=profile, group=group, starts_at=now-timedelta(hours=1), ends_at=now+timedelta(days=1), status='ACTIVE')
    return LocationShareGrant.objects.create(pilgrim=profile, trip=trip, consent_given=True, consent_version='phase-a-1', consent_timestamp=now-timedelta(minutes=1), enabled=True, expires_at=trip.ends_at)
