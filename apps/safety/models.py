from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile
from zones.models import Zone

class EmergencyContact(models.Model):
    SERVICE_CHOICES = [
        ('UNIFIED', _('Unified Security & Police (911)')),
        ('AMBULANCE', _('Red Crescent Medical (997)')),
        ('CIVIL_DEFENSE', _('Civil Defense & Rescue (998)')),
        ('HAJJ_CARE', _('Ministry of Hajj Pilgrim Care (1966)')),
        ('HEALTH_ADVICE', _('Ministry of Health Medical Advice (937)')),
    ]

    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    number = models.CharField(max_length=15)
    service_type = models.CharField(max_length=20, choices=SERVICE_CHOICES, default='UNIFIED')
    description_ar = models.CharField(max_length=255, blank=True)
    description_en = models.CharField(max_length=255, blank=True)
    badge_color = models.CharField(max_length=20, default="#dc3545")
    icon_name = models.CharField(max_length=50, default="bi-telephone-fill")
    sort_order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['sort_order']

    def __str__(self):
        return f"{self.name_en} ({self.number})"


class FieldUnit(models.Model):
    """
    KSU Specification Section 6:
    FieldUnit: name, type (medical, security or civil defence), current_zone, available
    """
    UNIT_TYPE_CHOICES = [
        ('MEDICAL', _('Red Crescent / Field Hospital Ambulance')),
        ('SECURITY', _('Haram / Hajj Security Forces')),
        ('CIVIL_DEFENSE', _('Civil Defense Rescue Unit')),
    ]

    name = models.CharField(max_length=150)
    unit_type = models.CharField(max_length=20, choices=UNIT_TYPE_CHOICES, default='MEDICAL')
    current_zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='field_units')
    available = models.BooleanField(default=True)
    phone = models.CharField(max_length=25, blank=True)
    radio_callsign = models.CharField(max_length=50, blank=True)

    def __str__(self):
        zone_name = self.current_zone.code if self.current_zone else "Roaming"
        status_str = "Available" if self.available else "Dispatched"
        return f"{self.name} [{self.get_unit_type_display()}] - {zone_name} ({status_str})"


class SosIncident(models.Model):
    """
    KSU Specification Section 6 & 7:
    SosReport: pilgrim, category, latitude, longitude, zone, status, assigned_unit, created, closed
    """
    CATEGORY_CHOICES = [
        ('MEDICAL', _('Medical Emergency / Heart / Fainting')),
        ('HEAT', _('Heat Stroke / Dehydration')),
        ('CRUSH', _('Crowd Stampede / Chokepoint')),
        ('LOST', _('Lost / Separated from Group')),
        ('GENERAL', _('General Emergency Help')),
    ]

    STATUS_CHOICES = [
        ('OPEN', _('Active / Help Requested')),
        ('RESPONDING', _('Dispatched / Unit En Route')),
        ('RESOLVED', _('Resolved / Safe')),
    ]

    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='sos_incidents')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='GENERAL')
    lat = models.FloatField()
    lng = models.FloatField()
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='sos_incidents')
    
    # Unit assignment (Section 6 & 7.2: Incident queue)
    assigned_unit = models.ForeignKey(FieldUnit, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    
    battery_level = models.PositiveIntegerField(null=True, blank=True, help_text="Phone battery % at time of SOS")
    called_number = models.CharField(max_length=15, blank=True, help_text="Direct emergency number dialed (e.g. 911, 997)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    notes = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(fields=['pilgrim', 'idempotency_key'], condition=~models.Q(idempotency_key=''), name='unique_sos_idempotency')]

    def __str__(self):
        unit_str = f"-> {self.assigned_unit.name}" if self.assigned_unit else "Unassigned"
        return f"SOS #{self.id} - {self.pilgrim.user.get_full_name() or self.pilgrim.user.username} ({self.category}) [{self.status}] {unit_str}"


class SosCallIntent(models.Model):
    """Records the pilgrim's explicit request to open the device dialer."""
    incident = models.ForeignKey(SosIncident, on_delete=models.CASCADE, related_name='call_intents')
    requested_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='sos_call_intents')
    number = models.CharField(max_length=15)
    requested_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=['incident', 'requested_at'])]


class IntegrationProvider(models.Model):
    """Provider registry; live use remains disabled until authorization is recorded."""
    ENVIRONMENTS = [('SANDBOX', 'Sandbox'), ('STAGING', 'Staging'), ('PRODUCTION', 'Production')]
    STATES = [('DISABLED', 'Disabled'), ('SANDBOX', 'Sandbox'), ('STAGING', 'Staging'), ('PRODUCTION', 'Production'), ('DEGRADED', 'Degraded'), ('REVOKED', 'Revoked')]
    key = models.CharField(max_length=80, unique=True)
    display_name = models.CharField(max_length=160)
    environment = models.CharField(max_length=20, choices=ENVIRONMENTS, default='SANDBOX')
    state = models.CharField(max_length=20, choices=STATES, default='DISABLED')
    capabilities = models.JSONField(default=list, blank=True)
    authorization_evidence = models.TextField(blank=True)
    last_health_check = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class IntegrationAuthorization(models.Model):
    provider = models.ForeignKey(IntegrationProvider, on_delete=models.CASCADE, related_name='authorizations')
    subject_reference = models.CharField(max_length=180, blank=True)
    scopes = models.JSONField(default=list, blank=True)
    policy_version = models.CharField(max_length=40)
    consented_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IntegrationEvent(models.Model):
    provider = models.ForeignKey(IntegrationProvider, on_delete=models.PROTECT, related_name='events')
    direction = models.CharField(max_length=20, choices=[('INBOUND', 'Inbound'), ('OUTBOUND', 'Outbound')])
    event_type = models.CharField(max_length=80)
    idempotency_key = models.CharField(max_length=100, unique=True)
    external_reference = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=30, default='PENDING')
    error_category = models.CharField(max_length=80, blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)


class Alert(models.Model):
    """
    KSU Specification Section 6 & 7:
    Alert: zone, type, severity, message Arabic, message English, created, acknowledged
    Feeds both the dashboard and the pilgrim page
    """
    ALERT_TYPE_CHOICES = [
        ('CROWD_SURGE', _('Severe Crowd Surge')),
        ('CHOKEPOINT', _('Corridor Chokepoint Detected')),
        ('HEAT_STRESS', _('High Radiant Heat Advisory')),
        ('GATE_RESTRICTION', _('Gate Ingress Diverted')),
    ]

    SEVERITY_CHOICES = [
        ('LOW', _('Advisory (Green/Yellow)')),
        ('MEDIUM', _('Caution (Orange)')),
        ('HIGH', _('High Risk (Red)')),
        ('CRITICAL', _('Life-Safety Emergency (Flashing Red)')),
    ]

    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=30, choices=ALERT_TYPE_CHOICES, default='CROWD_SURGE')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='HIGH')
    message_ar = models.CharField(max_length=255)
    message_en = models.CharField(max_length=255)
    acknowledged = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.zone.code}: {self.message_en}"
