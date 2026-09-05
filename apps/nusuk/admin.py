from django.contrib import admin
from nusuk.models import HajjCampaign, NusukCard, TafweejSchedule

@admin.register(HajjCampaign)
class HajjCampaignAdmin(admin.ModelAdmin):
    list_display = ('name_en', 'license_no', 'country', 'category', 'join_code', 'quota')
    list_filter = ('category', 'country')
    search_fields = ('name_en', 'name_ar', 'license_no', 'join_code')

@admin.register(NusukCard)
class NusukCardAdmin(admin.ModelAdmin):
    list_display = ('tasreeh_no', 'pilgrim', 'campaign', 'assigned_jamarat_floor', 'is_valid')
    list_filter = ('campaign', 'is_valid')
    search_fields = ('tasreeh_no', 'border_or_national_id', 'pilgrim__user__first_name')

@admin.register(TafweejSchedule)
class TafweejScheduleAdmin(admin.ModelAdmin):
    list_display = ('campaign', 'target_zone', 'slot_start', 'slot_end', 'allocated_pilgrim_count', 'status')
    list_filter = ('status', 'target_zone')
