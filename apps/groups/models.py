import secrets
from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile
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
