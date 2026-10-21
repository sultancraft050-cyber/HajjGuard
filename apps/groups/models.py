import secrets
from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile
from django.core.validators import MinValueValidator, MaxValueValidator
from nusuk.models import HajjCampaign

class PilgrimGroup(models.Model):
    name = models.CharField(max_length=150, help_text="Family or sub-group name, e.g., 'Al-Hashimi Family'")
    campaign = models.ForeignKey(HajjCampaign, on_delete=models.PROTECT, related_name='groups')
    leader = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='led_groups')
    join_code = models.CharField(
        max_length=12,
        unique=True,
        db_index=True,
        help_text="Collision-resilient 4-8 character code for family members to link to leader"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_join_code(cls, length=4, max_attempts=20):
        """
        Generates a collision-resilient unique join code.
        If a code collision occurs, regenerates in a retry loop.
        If collisions persist across max_attempts (e.g. key space saturation during peak Hajj),
        it automatically expands the code length by 1 character, guaranteeing termination.
        """
        current_len = length
        attempts = 0
        while True:
            # 4 hex chars = 65,536 combinations; 6 hex chars = 16.7M combinations
            num_bytes = max(2, (current_len + 1) // 2)
            candidate = secrets.token_hex(num_bytes)[:current_len].upper()
            if not cls.objects.filter(join_code=candidate).exists():
                return candidate
            attempts += 1
            if attempts >= max_attempts:
                current_len += 1
                attempts = 0

    def save(self, *args, **kwargs):
        if not self.join_code:
            self.join_code = self.generate_join_code()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} (Code: {self.join_code}) - Leader: {self.leader.user.get_full_name() or self.leader.user.username}"

class GroupMembership(models.Model):
    ROLE_CHOICES = [
        ('MEMBER', _('Group Member')),
        ('DEPUTY', _('Deputy Leader')),
        ('DEPENDENT', _('Elderly / Child Dependent')),
    ]

    group = models.ForeignKey(PilgrimGroup, on_delete=models.CASCADE, related_name='members')
    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='group_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='MEMBER')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('group', 'pilgrim')
        indexes = [
            models.Index(fields=['group', 'is_active']),
            models.Index(fields=['pilgrim', 'is_active']),
        ]

    def __str__(self):
        return f"{self.pilgrim.user.get_full_name() or self.pilgrim.user.username} in {self.group.name} ({self.role})"


class PilgrimTrip(models.Model):
    STATUS_CHOICES = [('PLANNED', _('Planned')), ('ACTIVE', _('Active')), ('ENDED', _('Ended')), ('CANCELLED', _('Cancelled'))]
    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='trips')
    group = models.ForeignKey(PilgrimGroup, on_delete=models.CASCADE, related_name='trips')
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PLANNED')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['pilgrim', 'status', 'ends_at']), models.Index(fields=['group', 'status', 'ends_at'])]


class LocationShareGrant(models.Model):
    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='location_share_grants')
    trip = models.OneToOneField(PilgrimTrip, on_delete=models.CASCADE, related_name='location_share')
    consent_given = models.BooleanField(default=False)
    consent_version = models.CharField(max_length=30, blank=True)
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)
    revoked_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        indexes = [models.Index(fields=['pilgrim', 'enabled', 'expires_at'])]

    @property
    def is_active(self):
        from django.utils import timezone
        return self.enabled and self.consent_given and not self.revoked_at and self.expires_at > timezone.now()


class GroupMessage(models.Model):
    group = models.ForeignKey(PilgrimGroup, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(PilgrimProfile, on_delete=models.PROTECT, related_name='group_messages')
    text = models.TextField(max_length=2000)
    image = models.ImageField(upload_to='group_messages/%Y/%m/', blank=True, null=True)
    is_announcement = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    reported = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=['group', 'created_at'])]


class GroupGeofence(models.Model):
    group = models.ForeignKey(PilgrimGroup, on_delete=models.CASCADE, related_name='geofences')
    trip = models.ForeignKey(PilgrimTrip, on_delete=models.CASCADE, related_name='geofences')
    name = models.CharField(max_length=120)
    center_lat = models.FloatField(validators=[MinValueValidator(-90), MaxValueValidator(90)])
    center_lng = models.FloatField(validators=[MinValueValidator(-180), MaxValueValidator(180)])
    radius_meters = models.PositiveIntegerField(default=100, validators=[MinValueValidator(20), MaxValueValidator(5000)])
    enabled = models.BooleanField(default=True)
    cooldown_seconds = models.PositiveIntegerField(default=300)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['group', 'enabled']), models.Index(fields=['trip', 'enabled'])]


class GeofenceAlert(models.Model):
    EVENT_CHOICES = [('ENTER', _('Entered')), ('EXIT', _('Exited'))]
    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='geofence_alerts')
    geofence = models.ForeignKey(GroupGeofence, on_delete=models.CASCADE, related_name='alerts')
    event_type = models.CharField(max_length=5, choices=EVENT_CHOICES)
    occurred_at = models.DateTimeField(auto_now_add=True, db_index=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['pilgrim', 'geofence', 'occurred_at'])]


class PhonePingRequest(models.Model):
    STATUS_CHOICES = [('PENDING', _('Pending')), ('DELIVERED', _('Delivered')), ('EXPIRED', _('Expired')), ('FAILED', _('Failed'))]
    requester = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='phone_ping_requests')
    target = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='phone_pings_received')
    group = models.ForeignKey(PilgrimGroup, on_delete=models.CASCADE, related_name='phone_ping_requests')
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['target', 'status', 'expires_at']), models.Index(fields=['requester', 'created_at'])]
