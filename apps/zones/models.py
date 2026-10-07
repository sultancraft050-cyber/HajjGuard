from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile
from zones.utils import haversine_distance

class Zone(models.Model):
    SITE_CHOICES = [
        ('HARAM', _('Masjid Al-Haram (Makkah)')),
        ('JAMARAT', _('Jamarat Stoning Complex')),
        ('MINA', _('Mina Camps')),
        ('MUZDALIFAH', _('Muzdalifah')),
        ('ARAFAT', _('Arafat Plain')),
    ]

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    site_type = models.CharField(max_length=20, choices=SITE_CHOICES, default='HARAM')
    
    # Coordinates and geometry (circles)
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    radius_meters = models.FloatField(
        default=60.0,
        validators=[MinValueValidator(1.0)],
        help_text="Radius in meters, must be at least 1.0m"
    )
    floor_level = models.IntegerField(default=0, help_text="0 for ground, 1 for first floor, etc.")
    
    # Capacity thresholds (protected against zero to prevent division-by-zero in density calculations)
    safe_capacity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Maximum comfortable capacity in headcount (min 1)"
    )
    floor_area_sqm = models.PositiveIntegerField(
        default=1000,
        validators=[MinValueValidator(1)],
        help_text="Floor area in square meters (min 1 sqm)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    def contains_point(self, lat, lng):
        """Returns True if the lat/lng point is inside the circular zone radius"""
        dist = haversine_distance(self.center_lat, self.center_lng, lat, lng)
        return dist <= self.radius_meters

    def distance_to(self, lat, lng):
        """Returns distance in meters to a given coordinate"""
        return haversine_distance(self.center_lat, self.center_lng, lat, lng)

    def get_status(self, current_count):
        """Returns status tuple (status_code, color_code, label) based on current count and seasonality"""
        if current_count <= 0 and self.site_type in ['JAMARAT', 'MINA', 'MUZDALIFAH', 'ARAFAT']:
            return ('DORMANT', '#6c757d', _('Off-Season / Closed (خارج موسم الحج)'))

        ratio = current_count / max(self.safe_capacity, 1)
        if ratio >= 1.0:
            return ('RED', '#dc3545', _('Congested / Extreme Caution'))
        elif ratio >= 0.7:
            return ('ORANGE', '#ffc107', _('Moderate / Busy'))
        else:
            return ('GREEN', '#198754', _('Comfortable / Normal'))

    def __str__(self):
        return f"{self.name_en} ({self.code})"

class Corridor(models.Model):
    name_ar = models.CharField(max_length=100)
    name_en = models.CharField(max_length=100)
    from_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='outgoing_corridors')
    to_zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='incoming_corridors')
    base_walking_minutes = models.FloatField(default=10.0, validators=[MinValueValidator(0.1)])
    width_meters = models.FloatField(default=15.0, validators=[MinValueValidator(1.0)])
    is_active = models.BooleanField(default=True)
    wheelchair_accessible = models.BooleanField(null=True, blank=True, help_text='Unknown until verified on site.')
    shaded = models.BooleanField(null=True, blank=True, help_text='Verified shade coverage; not a temperature measurement.')
    length_meters = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0.1)])
    verification_source = models.CharField(max_length=250, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['from_zone', 'to_zone', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name_en}: {self.from_zone.code} -> {self.to_zone.code} ({self.base_walking_minutes} min)"

class LocationPing(models.Model):
    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='pings')
    lat = models.FloatField()
    lng = models.FloatField()
    accuracy_meters = models.FloatField(null=True, blank=True, help_text="Device-reported horizontal accuracy in meters")
    altitude = models.FloatField(null=True, blank=True, help_text="Barometric or GPS altitude in meters")
    floor_level = models.IntegerField(default=0, help_text="Estimated floor level (0=Ground, 1=Level 1, etc.)")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='pings')
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['pilgrim', 'timestamp']),
            models.Index(fields=['zone', 'timestamp']),
        ]

    def __str__(self):
        return f"Ping by {self.pilgrim} at {self.timestamp.strftime('%H:%M:%S')}"

class DensityRecord(models.Model):
    STATUS_CHOICES = [
        ('GREEN', _('Normal')),
        ('ORANGE', _('Busy')),
        ('RED', _('Congested')),
    ]

    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='density_records')
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    phone_count = models.PositiveIntegerField(default=0)
    image_count = models.PositiveIntegerField(default=0)
    total_people = models.PositiveIntegerField(default=0)
    density_per_sqm = models.FloatField(default=0.0)
    predicted_density_20m = models.FloatField(default=0.0)
    risk_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='GREEN')

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['zone', 'timestamp']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['status', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.zone.code} at {self.timestamp.strftime('%H:%M:%S')} - {self.status} (Density: {self.density_per_sqm:.2f} p/m²)"


class CameraSnapshot(models.Model):
    """
    KSU Specification Section 6 & 16:
    CameraSnapshot: zone, taken_at, people_counted, processed
    Note: The image file itself is deleted immediately after inference (PDPL compliance).
    """
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='camera_snapshots')
    taken_at = models.DateTimeField(default=timezone.now, db_index=True)
    people_counted = models.PositiveIntegerField(default=0)
    processed = models.BooleanField(default=True)
    source_label = models.CharField(max_length=100, default='Optical CCTV Sensor')

    class Meta:
        ordering = ['-taken_at']

    def __str__(self):
        return f"Snapshot @ {self.zone.code} ({self.taken_at.strftime('%H:%M:%S')}): {self.people_counted} detected"


class SafetyMapFeature(models.Model):
    CATEGORIES = [(k, k.replace('_', ' ').title()) for k in (
        'TOILET', 'WATER', 'MEDICAL', 'FIRST_AID', 'WHEELCHAIR_ROUTE',
        'REST', 'ENTRANCE', 'EXIT', 'SHUTTLE', 'TRAIN', 'RESTRICTED')]
    name = models.CharField(max_length=160)
    category = models.CharField(max_length=25, choices=CATEGORIES)
    coordinates = models.JSONField(help_text='One or more [latitude, longitude] pairs. Routes require at least two.')
    source = models.CharField(max_length=250, help_text='Survey or public dataset reference; no personal data.')
    verified_at = models.DateTimeField(null=True, blank=True)
    enabled = models.BooleanField(default=False)

    def clean(self):
        import math
        from django.core.exceptions import ValidationError
        super().clean()
        try:
            if not self.coordinates or not isinstance(self.coordinates, list):
                raise ValueError()
            for pair in self.coordinates:
                if len(pair) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in pair):
                    raise ValueError()
                if not -90 <= pair[0] <= 90 or not -180 <= pair[1] <= 180:
                    raise ValueError()
            if self.category == 'WHEELCHAIR_ROUTE' and len(self.coordinates) < 2:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValidationError({'coordinates': 'Supply finite coordinates within valid ranges.'})
        if self.enabled and (not self.source.strip() or self.verified_at is None):
            raise ValidationError('Enabled features require a source and verification timestamp.')

    def __str__(self):
        return self.name


class VisitorPlace(models.Model):
    """Source-labelled public places for visitor planning.

    This is a directory, not an inventory or booking system. Availability and
    pricing are deliberately outside the model and must be verified by visitors.
    """
    CATEGORY_CHOICES = [
        ('STAY', _('Stay')),
        ('VISIT', _('Visit')),
        ('TRANSPORT', _('Transport')),
        ('ESSENTIAL', _('Food and essentials')),
        ('ACCESSIBILITY', _('Accessibility')),
        ('SAFETY', _('Safety')),
    ]
    name_ar = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, db_index=True)
    description = models.TextField()
    area = models.CharField(max_length=160, blank=True)
    coordinates = models.JSONField(null=True, blank=True, help_text='[latitude, longitude]')
    address = models.CharField(max_length=240, blank=True)
    accessibility = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=250)
    source_url = models.URLField(blank=True)
    verification_date = models.DateField(null=True, blank=True, db_index=True)
    enabled = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'name_en']
        indexes = [models.Index(fields=['enabled', 'category'])]

    def clean(self):
        import math
        from django.core.exceptions import ValidationError
        super().clean()
        if self.coordinates is not None:
            valid = (
                isinstance(self.coordinates, list) and len(self.coordinates) == 2 and
                all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                    for value in self.coordinates) and
                -90 <= self.coordinates[0] <= 90 and -180 <= self.coordinates[1] <= 180
            )
            if not valid:
                raise ValidationError({'coordinates': 'Use [latitude, longitude] with finite valid values.'})
        if self.enabled:
            if not self.coordinates:
                raise ValidationError({'coordinates': 'Enabled visitor places require coordinates.'})
            if not self.source.strip() or self.verification_date is None:
                raise ValidationError('Enabled visitor places require a source and verification date.')
            if self.verification_date > timezone.localdate():
                raise ValidationError({'verification_date': 'Verification date cannot be in the future.'})
        if self.accessibility is not None and not isinstance(self.accessibility, dict):
            raise ValidationError({'accessibility': 'Accessibility must be a JSON object.'})

    @property
    def is_stale(self):
        if not self.verification_date:
            return True
        return (timezone.localdate() - self.verification_date).days > 90

    def __str__(self):
        return self.name_en

