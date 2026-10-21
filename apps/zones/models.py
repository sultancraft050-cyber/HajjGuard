from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile
from zones.utils import haversine_distance

# Public map plausibility bounds. These cover the live Makkah/Holy Site
# records and every existing test fixture while rejecting swapped coordinates
# and clearly out-of-region points. They are a review guard, not a navigation
# boundary.
MAP_LAT_MIN, MAP_LAT_MAX = 21.30, 21.50
MAP_LNG_MIN, MAP_LNG_MAX = 39.75, 40.10


def validate_public_map_point(latitude, longitude):
    import math
    from django.core.exceptions import ValidationError

    if latitude is None or longitude is None:
        raise ValidationError('Public map records require latitude and longitude.')
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
           for value in (latitude, longitude)):
        raise ValidationError('Public map coordinates must be finite numbers.')
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        raise ValidationError('Coordinates must be within valid latitude/longitude ranges.')
    if latitude == 0 and longitude == 0:
        raise ValidationError('The (0,0) coordinate is not a valid public map location.')
    if not MAP_LAT_MIN <= latitude <= MAP_LAT_MAX or not MAP_LNG_MIN <= longitude <= MAP_LNG_MAX:
        raise ValidationError('Coordinates are outside the supported Makkah map area.')

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

    def clean(self):
        super().clean()
        validate_public_map_point(self.center_lat, self.center_lng)

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
    source_url = models.URLField(blank=True, help_text='Public evidence URL; never include private credentials.')
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
                validate_public_map_point(pair[0], pair[1])
            if self.category == 'WHEELCHAIR_ROUTE' and len(self.coordinates) < 2:
                raise ValueError()
        except (TypeError, ValueError):
            raise ValidationError({'coordinates': 'Supply finite coordinates within valid ranges.'})
        if self.enabled and (not self.source.strip() or self.verified_at is None):
            raise ValidationError('Enabled features require a source and verification timestamp.')

    def __str__(self):
        return self.name


class HaramLocation(models.Model):
    """Floor-aware Haram points for the local 3D location explorer.

    Records are disabled until their source and placement have been reviewed.
    This inventory intentionally stores public places only; it is not a person
    or telemetry model.
    """
    CATEGORY_CHOICES = [
        ('GATE', 'Gate'), ('MATAF', 'Mataf'), ('MASAA', 'Masaa'),
        ('WATER', 'Water'), ('TOILET', 'Toilet'), ('MEDICAL', 'Medical'),
        ('WHEELCHAIR_ACCESS', 'Wheelchair access'), ('ELEVATOR', 'Elevator'),
        ('ESCALATOR', 'Escalator'), ('STAIRS', 'Stairs'),
        ('MEETING_POINT', 'Meeting point'), ('EMERGENCY_EXIT', 'Emergency exit'),
        ('INFORMATION_DESK', 'Information desk'),
    ]
    ACCURACY_CHOICES = [('UNVERIFIED', 'Unverified'), ('APPROXIMATE', 'Approximate'), ('VERIFIED', 'Verified')]

    location_id = models.CharField(max_length=80, unique=True, db_index=True)
    name_ar = models.CharField(max_length=180)
    name_en = models.CharField(max_length=180)
    available_languages = models.JSONField(default=list, blank=True)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, db_index=True)
    floor_level = models.IntegerField(default=0, help_text='0 ground, 1 first, 2 roof; use -1 for basement.')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    local_x = models.FloatField(null=True, blank=True)
    local_y = models.FloatField(null=True, blank=True)
    local_z = models.FloatField(null=True, blank=True)
    source = models.CharField(max_length=250, blank=True)
    source_url = models.URLField(blank=True)
    verification_date = models.DateField(null=True, blank=True)
    accuracy_level = models.CharField(max_length=15, choices=ACCURACY_CHOICES, default='UNVERIFIED')
    enabled = models.BooleanField(default=False, db_index=True)
    notes = models.TextField(blank=True, help_text='Public location notes only; never include private information.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['floor_level', 'category', 'name_en']
        indexes = [models.Index(fields=['enabled', 'floor_level', 'category'])]

    def clean(self):
        import math
        from django.core.exceptions import ValidationError
        super().clean()
        if not isinstance(self.available_languages, list) or any(not isinstance(value, str) or not value.strip() for value in self.available_languages):
            raise ValidationError({'available_languages': 'Use a list of available language codes.'})
        for field_name, value, low, high in (
            ('latitude', self.latitude, -90, 90), ('longitude', self.longitude, -180, 180),
        ):
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high):
                raise ValidationError({field_name: 'Use a finite coordinate within the valid range.'})
        if self.latitude is not None and self.longitude is not None:
            validate_public_map_point(self.latitude, self.longitude)
        import re
        if len(set(self.available_languages)) != len(self.available_languages) or any(not re.fullmatch(r'[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*', v) for v in self.available_languages):
            raise ValidationError({'available_languages': 'Use unique language codes such as ar, en, ur or id.'})
        for field in ('local_x', 'local_y', 'local_z'):
            value = getattr(self, field)
            if value is not None and (isinstance(value, bool) or not math.isfinite(value)):
                raise ValidationError({field: 'Use a finite number.'})
        if self.enabled:
            if self.accuracy_level == 'UNVERIFIED':
                raise ValidationError({'accuracy_level': 'Unverified locations must remain disabled.'})
            if self.latitude is None or self.longitude is None or any(getattr(self, field) is None for field in ('local_x', 'local_y', 'local_z')):
                raise ValidationError('Enabled Haram locations require geographic and 3D positions.')
            if not self.source.strip() or self.verification_date is None:
                raise ValidationError('Enabled Haram locations require a source and verification date.')
            if self.verification_date > timezone.localdate():
                raise ValidationError({'verification_date': 'Verification date cannot be in the future.'})

    def __str__(self):
        return f'{self.location_id} · {self.name_en}'


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
            try:
                validate_public_map_point(self.coordinates[0], self.coordinates[1])
            except ValidationError as exc:
                raise ValidationError({'coordinates': exc.messages})
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

