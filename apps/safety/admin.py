from django.contrib import admin
from safety.models import EmergencyContact, SosIncident

@admin.register(EmergencyContact)
class EmergencyContactAdmin(admin.ModelAdmin):
    list_display = ('number', 'name_en', 'service_type', 'sort_order')
    list_editable = ('sort_order',)

@admin.register(SosIncident)
class SosIncidentAdmin(admin.ModelAdmin):
    list_display = ('id', 'pilgrim', 'category', 'zone', 'called_number', 'status', 'created_at')
    list_filter = ('status', 'category', 'zone')
    search_fields = ('pilgrim__user__username', 'pilgrim__user__first_name', 'notes')
