import io
import json
import qrcode
from django.db import models
from django.core.files.base import ContentFile
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile
from zones.models import Zone

class HajjCampaign(models.Model):
    CATEGORY_CHOICES = [
        ('ECONOMIC', _('Economic / Hospitality')),
        ('STANDARD', _('Standard')),
        ('PREMIUM', _('VIP / Towers')),
    ]

    license_no = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=200)
    name_en = models.CharField(max_length=200)
    country = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='STANDARD')
    
    # Camp & logistics allocations
    assigned_mina_sector = models.CharField(max_length=100, default="Sector 3")
    mina_camp_no = models.CharField(max_length=50, default="Camp 44")
    makkah_hotel = models.CharField(max_length=150, blank=True)
    
    # Leadership and contacts
    leader_name = models.CharField(max_length=120)
    leader_phone = models.CharField(max_length=25)
    quota = models.PositiveIntegerField(default=1000)
    join_code = models.CharField(max_length=10, unique=True, db_index=True, help_text="Short code pilgrims enter to join")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name_en} ({self.license_no}) - Code: {self.join_code}"

class NusukCard(models.Model):
    pilgrim = models.OneToOneField(PilgrimProfile, on_delete=models.CASCADE, related_name='nusuk_card')
    # Use PROTECT to prevent catastrophic cascade deletion of pilgrims' official smart cards
    campaign = models.ForeignKey(HajjCampaign, on_delete=models.PROTECT, related_name='pilgrims')
    tasreeh_no = models.CharField(max_length=50, unique=True, db_index=True)
    border_or_national_id = models.CharField(max_length=50, db_index=True)
    
    # Logistics
    tafweej_jamarat_slot = models.CharField(max_length=100, default="10 Dhul-Hijjah 09:00 - 10:00")
    assigned_jamarat_floor = models.IntegerField(default=2, help_text="Target floor: 0=Ground, 1=1st, 2=2nd, 3=3rd")
    tent_street_no = models.CharField(max_length=50, blank=True, default='Street 204')
    makkah_hotel_name = models.CharField(max_length=150, blank=True, default='Abraj Al-Bait / Jabal Omar')
    photo_url = models.CharField(max_length=255, blank=True, default='')
    barcode_code = models.CharField(max_length=64, blank=True, default='')
    emergency_pin = models.CharField(max_length=10, blank=True, default='992144')
    
    # Verification and QR
    qr_payload = models.TextField(blank=True)
    qr_code_image = models.ImageField(upload_to='nusuk_qrs/', blank=True, null=True)
    is_valid = models.BooleanField(default=True)
    issued_at = models.DateTimeField(auto_now_add=True)

    def get_barcode_code(self):
        if not self.barcode_code:
            clean_tasreeh = self.tasreeh_no.replace('-', '').replace(' ', '')
            self.barcode_code = f"NSK{clean_tasreeh[-8:]}"
        return self.barcode_code

    def generate_qr_payload(self):
        payload = {
            "type": "NUSUK_SMART_CARD",
            "version": "2.0-2026",
            "tasreeh_no": self.tasreeh_no,
            "pilgrim_id": self.border_or_national_id,
            "name": self.pilgrim.user.get_full_name() or self.pilgrim.user.username,
            "nationality": getattr(self.pilgrim, 'nationality', 'Saudi Arabia'),
            "campaign_id": self.campaign.license_no,
            "campaign_name": self.campaign.name_en,
            "camp": f"{self.campaign.assigned_mina_sector} - {self.campaign.mina_camp_no} ({self.tent_street_no})",
            "leader_phone": self.campaign.leader_phone,
            "blood_type": self.pilgrim.blood_type,
            "is_vulnerable": self.pilgrim.is_vulnerable(),
            "emergency_pin": self.emergency_pin,
            "barcode": self.get_barcode_code(),
            "jamarat_slot": self.tafweej_jamarat_slot,
            "jamarat_floor": self.assigned_jamarat_floor
        }
        self.qr_payload = json.dumps(payload, ensure_ascii=False)
        return self.qr_payload

    def save(self, *args, **kwargs):
        if not self.barcode_code:
            self.get_barcode_code()
        if not self.qr_payload:
            self.generate_qr_payload()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Nusuk Card [{self.tasreeh_no}] - {self.pilgrim.user.get_full_name() or self.pilgrim.user.username}"

class TafweejSchedule(models.Model):
    STATUS_CHOICES = [
        ('SCHEDULED', _('Scheduled')),
        ('ACTIVE', _('In Progress / Moving')),
        ('COMPLETED', _('Completed')),
        ('DELAYED', _('Delayed / Hold')),
    ]

    campaign = models.ForeignKey(HajjCampaign, on_delete=models.PROTECT, related_name='tafweej_slots')
    target_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='tafweej_schedules')
    slot_start = models.DateTimeField(db_index=True)
    slot_end = models.DateTimeField(db_index=True)
    allocated_pilgrim_count = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='SCHEDULED')

    class Meta:
        indexes = [
            models.Index(fields=['campaign', 'slot_start']),
            models.Index(fields=['target_zone', 'slot_start']),
        ]

    def __str__(self):
        return f"Tafweej: {self.campaign.name_en} -> {self.target_zone.code} ({self.status})"
