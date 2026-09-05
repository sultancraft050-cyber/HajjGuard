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

class SosIncident(models.Model):
    CATEGORY_CHOICES = [
        ('MEDICAL', _('Medical Emergency / Heart / Fainting')),
        ('HEAT', _('Heat Stroke / Dehydration')),
        ('CRUSH', _('Crowd Stampede / Chokepoint')),
        ('LOST', _('Lost / Separated from Group')),
        ('GENERAL', _('General Emergency Help')),
    ]

    STATUS_CHOICES = [
        ('OPEN', _('Active / Help Requested')),
        ('RESPONDING', _('Emergency Services Contacted')),
        ('RESOLVED', _('Resolved / Safe')),
    ]

    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='sos_incidents')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='GENERAL')
    lat = models.FloatField()
    lng = models.FloatField()
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='sos_incidents')
    
    battery_level = models.PositiveIntegerField(null=True, blank=True, help_text="Phone battery % at time of SOS")
    called_number = models.CharField(max_length=15, blank=True, help_text="Direct emergency number dialed (e.g. 911, 997)")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"SOS #{self.id} - {self.pilgrim.user.get_full_name() or self.pilgrim.user.username} ({self.category}) - {self.status}"

