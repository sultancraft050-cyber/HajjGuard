from django.urls import path
from . import views
from .pwa_views import live_members, messages, create_message, list_geofences, phone_ping, acknowledge_geofence, my_geofence_alerts

app_name = 'groups'

urlpatterns = [
    path('my-group/', views.my_group_view, name='my_group'),
    path('lost-pilgrim/', views.lost_pilgrim_lookup_view, name='lost_pilgrim'),
    path('api/join/', views.api_join_group, name='api_join_group'),
    path('api/groups/<int:group_id>/live-members/', live_members, name='live_members'),
    path('api/groups/<int:group_id>/messages/', messages, name='messages'),
    path('api/groups/<int:group_id>/messages/create/', create_message, name='create_message'),
    path('api/groups/<int:group_id>/geofences/', list_geofences, name='list_geofences'),
    path('api/groups/<int:group_id>/members/<int:member_id>/ping/', phone_ping, name='phone_ping'),
    path('api/geofences/<int:geofence_id>/acknowledge/', acknowledge_geofence, name='acknowledge_geofence'),
    path('api/geofence-alerts/', my_geofence_alerts, name='my_geofence_alerts'),
]
