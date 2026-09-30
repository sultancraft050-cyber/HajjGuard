from django.contrib import admin
from zones.models import Zone, Corridor, LocationPing, DensityRecord, CameraSnapshot, SafetyMapFeature

@admin.register(SafetyMapFeature)
class SafetyMapFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'source', 'verified_at', 'enabled')
    list_filter = ('category', 'enabled')

@admin.register(Zone)
class ZoneAdmin(admin.ModelAdmin):
    list_display = ('code', 'name_en', 'site_type', 'floor_level', 'safe_capacity', 'center_lat', 'center_lng')
    list_filter = ('site_type', 'floor_level')
    search_fields = ('code', 'name_en', 'name_ar')

@admin.register(Corridor)
class CorridorAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'from_zone', 'to_zone', 'base_walking_minutes', 'width_meters', 'is_active')
    list_filter = ('is_active',)

@admin.register(LocationPing)
class LocationPingAdmin(admin.ModelAdmin):
    list_display = ('pilgrim', 'zone', 'lat', 'lng', 'timestamp')
    list_filter = ('zone', 'timestamp')

@admin.register(DensityRecord)
class DensityRecordAdmin(admin.ModelAdmin):
    list_display = ('zone', 'total_people', 'density_per_sqm', 'predicted_density_20m', 'status', 'risk_score', 'timestamp')
    list_filter = ('status', 'zone')

@admin.register(CameraSnapshot)
class CameraSnapshotAdmin(admin.ModelAdmin):
    list_display = ('zone', 'people_counted', 'processed', 'source_label', 'taken_at')
    list_filter = ('zone', 'processed')
