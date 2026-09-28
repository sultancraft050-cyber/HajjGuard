from django.contrib import admin
from .models import PilgrimGroup, GroupMembership

class GroupMembershipInline(admin.TabularInline):
    model = GroupMembership
    extra = 1

@admin.register(PilgrimGroup)
class PilgrimGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'join_code', 'leader', 'campaign', 'created_at')
    search_fields = ('name', 'join_code', 'leader__user__username')
    inlines = [GroupMembershipInline]

@admin.register(GroupMembership)
class GroupMembershipAdmin(admin.ModelAdmin):
    list_display = ('pilgrim', 'group', 'role', 'is_active', 'joined_at')
    list_filter = ('role', 'is_active')
