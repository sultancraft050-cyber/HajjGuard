from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from django.utils import timezone

class PilgrimProfile(models.Model):
    ROLE_CHOICES = [
        ('pilgrim', _('Pilgrim')),
        ('operator', _('Operations Staff')),
        ('group_leader', _('Group Leader')),
        ('field_unit', _('Field Unit / Paramedic')),
    ]

    LANGUAGE_CHOICES = [
        ('ar', 'العربية (Arabic)'),
        ('en', 'English'),
        ('ur', 'اردو (Urdu)'),
        ('id', 'Bahasa Indonesia'),
    ]

    CHRONIC_CHOICES = [
        ('NONE', _('None / Healthy')),
        ('CARDIAC', _('Heart Condition / High Blood Pressure')),
        ('DIABETES', _('Diabetes')),
        ('ASTHMA', _('Respiratory / Asthma')),
        ('OTHER', _('Other')),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='pilgrim')
    phone = models.CharField(max_length=25, blank=True)
    language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='ar')
    nationality = models.CharField(max_length=50, default='Saudi Arabia', blank=True)
    
    # Demographic and medical attributes (feeds Section 3 F2 risk score)
    age = models.PositiveIntegerField(default=30)
    gender = models.CharField(max_length=10, choices=[('M', _('Male')), ('F', _('Female'))], default='M')
    is_wheelchair_user = models.BooleanField(default=False)
    chronic_condition = models.CharField(max_length=50, choices=CHRONIC_CHOICES, default='NONE')
    blood_type = models.CharField(max_length=5, default='O+')
    
    # Official QR identifier payload (Section 6: QR code)
    qr_code_payload = models.CharField(max_length=255, blank=True, help_text="Unique QR identity payload")
    
    # PDPL Compliance: Consent record (Section 16)
    # Consent must be an explicit, recorded choice.  New profiles start
    # without consent and therefore cannot be treated as opted in.
    consent_given = models.BooleanField(default=False, help_text="Explicit consent for the selected HajjGuard processing purposes")
    consent_timestamp = models.DateTimeField(null=True, blank=True)
    
    # Emergency contact (son, daughter, relative)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=25, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def is_vulnerable(self):
        """Returns True if pilgrim is elderly (>=65) or has mobility/health vulnerabilities"""
        return self.age >= 65 or self.is_wheelchair_user or self.chronic_condition in ['CARDIAC', 'ASTHMA']

    def save(self, *args, **kwargs):
        if not self.qr_code_payload:
            self.qr_code_payload = f"HAJJGUARD-PILGRIM-{self.user.id}-{self.user.username.upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class AuditLog(models.Model):
    """
    KSU Specification Section 6 & 16 (PDPL Control):
    Every time a staff member opens a pilgrim record, a row is written to this audit table.
    """
    ACTION_CHOICES = [
        ('VIEW_PILGRIM', _('Viewed Pilgrim Record')),
        ('SCAN_QR', _('Scanned Lost Pilgrim QR')),
        ('EXPORT_REPORT', _('Exported Operations CSV')),
        ('ASSIGN_TICKET', _('Assigned Field Unit')),
        ('RESOLVE_INCIDENT', _('Resolved SOS Ticket')),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target = models.CharField(max_length=255, help_text="Identifier of viewed pilgrim, record or action target")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['user', 'timestamp']),
        ]

    def __str__(self):
        username = self.user.username if self.user else 'System'
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {username}: {self.get_action_display()} ({self.target})"
