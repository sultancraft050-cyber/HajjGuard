from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

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
    
    # Demographic and medical attributes
    age = models.PositiveIntegerField(default=30)
    gender = models.CharField(max_length=10, choices=[('M', _('Male')), ('F', _('Female'))], default='M')
    is_wheelchair_user = models.BooleanField(default=False)
    chronic_condition = models.CharField(max_length=50, choices=CHRONIC_CHOICES, default='NONE')
    blood_type = models.CharField(max_length=5, default='O+')
    
    # Emergency contact (son, daughter, relative)
    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=25, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def is_vulnerable(self):
        """Returns True if pilgrim is elderly (>=65) or has mobility/health vulnerabilities"""
        return self.age >= 65 or self.is_wheelchair_user or self.chronic_condition in ['CARDIAC', 'ASTHMA']

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"

