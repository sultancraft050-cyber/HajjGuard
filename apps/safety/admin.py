from django.contrib import admin
from safety.models import EmergencyContact, SosIncident, FieldUnit, Alert

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ('number', 'name_en', 'service_type', 'sort_order')
    list_editable = ('sort_order',)

@admin.register(FieldUnit)
class FieldUnitAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit_type', 'current_zone', 'available', 'phone', 'radio_callsign')
    list_filter = ('unit_type', 'available', 'current_zone')
    search_fields = ('name', 'radio_callsign', 'phone')

@admin.register(SosIncident)
class SosIncidentAdmin(admin.ModelAdmin):
    list_display = ('id', 'pilgrim', 'category', 'zone', 'assigned_unit', 'status', 'created_at')
    list_filter = ('status', 'category', 'zone', 'assigned_unit')
    search_fields = ('pilgrim__user__username', 'pilgrim__user__first_name', 'notes')

@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ('id', 'zone', 'alert_type', 'severity', 'message_en', 'acknowledged', 'created_at')
    list_filter = ('severity', 'alert_type', 'acknowledged', 'zone')
    search_fields = ('message_en', 'message_ar', 'zone__code')
