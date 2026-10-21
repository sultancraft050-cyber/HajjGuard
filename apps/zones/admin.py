from django.contrib import admin
from zones.models import Zone, Corridor, LocationPing, DensityRecord, CameraSnapshot, SafetyMapFeature, VisitorPlace


@admin.register(VisitorPlace)
class VisitorPlaceAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'category', 'area', 'verification_date', 'enabled')
    list_filter = ('category', 'enabled')
    search_fields = ('name_en', 'name_ar', 'area', 'source')

@admin.register(SafetyMapFeature)
class SafetyMapFeatureAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'source', 'verified_at', 'enabled')
    list_filter = ('category', 'enabled')
    search_fields = ('name', 'source', 'source_url')

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


from zones.models import HaramLocation
from django.contrib import messages

@admin.register(HaramLocation)
class HaramLocationAdmin(admin.ModelAdmin):
    list_display = ('location_id', 'name_en', 'category', 'floor_level', 'accuracy_level', 'enabled', 'verification_date')
    search_fields = ('location_id', 'name_ar', 'name_en', 'source', 'category')
    list_filter = ('category', 'floor_level', 'accuracy_level', 'enabled', 'verification_date')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        ('Identity', {'fields': ('location_id', 'name_ar', 'name_en', 'available_languages', 'category', 'floor_level')}),
        ('Geographic position', {'fields': ('latitude', 'longitude')}),
        ('Haram model position', {'fields': ('local_x', 'local_y', 'local_z'), 'description': 'Coordinates relative to the Haram architecture origin, in model units. Geometry is illustrative.'}),
        ('Evidence and publication', {'fields': ('source', 'source_url', 'verification_date', 'accuracy_level', 'enabled', 'notes')}),
        ('History', {'fields': ('created_at', 'updated_at')}),
    )

    def save_model(self, request, obj, form, change):
        obj.full_clean()
        super().save_model(request, obj, form, change)
        if obj.enabled and obj.accuracy_level == 'APPROXIMATE':
            self.message_user(request, 'Published as approximate. This location is not confirmed as exact.', level=messages.WARNING)
