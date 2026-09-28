from django.contrib import admin
from accounts.models import PilgrimProfile, AuditLog

@admin.register(PilgrimProfile)
class PilgrimProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'language', 'nationality', 'age', 'is_wheelchair_user', 'chronic_condition', 'blood_type')
    list_filter = ('role', 'language', 'is_wheelchair_user', 'chronic_condition')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone', 'qr_code_payload')

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'user', 'action', 'target', 'ip_address')
    list_filter = ('action', 'timestamp')
    search_fields = ('user__username', 'target', 'action')
    readonly_fields = ('timestamp', 'user', 'action', 'target', 'ip_address')
