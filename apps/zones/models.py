import math
from django.db import models
from django.utils.translation import gettext_lazy as _
from accounts.models import PilgrimProfile

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate the great circle distance in meters between two points 
    on the earth (specified in decimal degrees)
    """
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

class Zone(models.Model):
    SITE_CHOICES = [
        ('HARAM', _('Masjid Al-Haram (Makkah)')),
        ('JAMARAT', _('Jamarat Stoning Complex')),
        ('MINA', _('Mina Camps')),
        ('MUZDALIFAH', _('Muzdalifah')),
        ('ARAFAT', _('Arafat Plain')),
    ]

    code = models.CharField(max_length=50, unique=True)
    name_ar = models.CharField(max_length=150)
    name_en = models.CharField(max_length=150)
    site_type = models.CharField(max_length=20, choices=SITE_CHOICES, default='HARAM')
    
    # Coordinates and geometry (circles)
    center_lat = models.FloatField()
    center_lng = models.FloatField()
    radius_meters = models.FloatField(default=60.0)
    floor_level = models.IntegerField(default=0, help_text="0 for ground, 1 for first floor, etc.")
    
    # Capacity thresholds
    safe_capacity = models.PositiveIntegerField(help_text="Maximum comfortable capacity in headcount")
    floor_area_sqm = models.PositiveIntegerField(default=1000)
    
    created_at = models.DateTimeField(auto_now_add=True)

    def contains_point(self, lat, lng):
        """Returns True if the lat/lng point is inside the circular zone radius"""
        dist = haversine_distance(self.center_lat, self.center_lng, lat, lng)
        return dist <= self.radius_meters

    def distance_to(self, lat, lng):
        """Returns distance in meters to a given coordinate"""
        return haversine_distance(self.center_lat, self.center_lng, lat, lng)

    def get_status(self, current_count):
        """Returns status tuple (status_code, color_code, label) based on current count"""
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
    base_walking_minutes = models.FloatField(default=10.0)
    width_meters = models.FloatField(default=15.0)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name_en}: {self.from_zone.code} -> {self.to_zone.code} ({self.base_walking_minutes} min)"

class LocationPing(models.Model):
    pilgrim = models.ForeignKey(PilgrimProfile, on_delete=models.CASCADE, related_name='pings')
    lat = models.FloatField()
    lng = models.FloatField()
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='pings')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['timestamp']),
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
    timestamp = models.DateTimeField(auto_now_add=True)
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
        ]

    def __str__(self):
        return f"{self.zone.code} at {self.timestamp.strftime('%H:%M:%S')} - {self.status} (Density: {self.density_per_sqm:.2f} p/m²)"

