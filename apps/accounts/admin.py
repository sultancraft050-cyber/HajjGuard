from django.contrib import admin
from accounts.models import PilgrimProfile

@admin.register(PilgrimProfile)
class PilgrimProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'language', 'age', 'is_wheelchair_user', 'chronic_condition', 'blood_type')
    list_filter = ('role', 'language', 'is_wheelchair_user', 'chronic_condition')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'phone')
