from django.urls import path
from . import views
from .pwa_views import (
    live_members, messages, create_message, list_geofences, phone_ping,
    acknowledge_geofence, my_geofence_alerts, group_management,
    create_announcement, remove_member, update_member_role, rotate_join_code,
    update_geofence, delete_geofence, upload_attachment, attachment, moderate_message,
)

app_name = 'groups'

urlpatterns = [
    path('my-group/', views.my_group_view, name='my_group'),
    path('lost-pilgrim/', views.lost_pilgrim_lookup_view, name='lost_pilgrim'),
    path('api/join/', views.api_join_group, name='api_join_group'),
    path('api/groups/<int:group_id>/live-members/', live_members, name='live_members'),
    path('api/groups/<int:group_id>/messages/', messages, name='messages'),
    path('api/groups/<int:group_id>/messages/create/', create_message, name='create_message'),
    path('api/groups/<int:group_id>/messages/<int:message_id>/attachment/', attachment, name='attachment'),
    path('api/groups/<int:group_id>/messages/<int:message_id>/attachments/', upload_attachment, name='upload_attachment'),
    path('api/groups/<int:group_id>/messages/<int:message_id>/moderate/', moderate_message, name='moderate_message'),
    path('api/groups/<int:group_id>/management/', group_management, name='group_management'),
    path('api/groups/<int:group_id>/announcements/', create_announcement, name='create_announcement'),
    path('api/groups/<int:group_id>/members/<int:member_id>/remove/', remove_member, name='remove_member'),
    path('api/groups/<int:group_id>/members/<int:member_id>/role/', update_member_role, name='update_member_role'),
    path('api/groups/<int:group_id>/rotate-code/', rotate_join_code, name='rotate_join_code'),
    path('api/groups/<int:group_id>/geofences/', list_geofences, name='list_geofences'),
    path('api/geofences/<int:geofence_id>/', update_geofence, name='update_geofence'),
    path('api/geofences/<int:geofence_id>/delete/', delete_geofence, name='delete_geofence'),
    path('api/groups/<int:group_id>/members/<int:member_id>/ping/', phone_ping, name='phone_ping'),
    path('api/geofences/<int:geofence_id>/acknowledge/', acknowledge_geofence, name='acknowledge_geofence'),
    path('api/geofence-alerts/', my_geofence_alerts, name='my_geofence_alerts'),
]
