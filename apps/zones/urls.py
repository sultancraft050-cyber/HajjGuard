from django.urls import path
from . import views

app_name = 'zones'

urlpatterns = [
    path('api/safety-features/', views.api_safety_features, name='api_safety_features'),
    path('map/', views.live_map_view, name='live_map'),
    path('live-map/', views.live_map_view, name='live_map_alias'),
    path('detail/<str:zone_id>/', views.zone_detail_view, name='zone_detail'),
    path('guidance/', views.guidance_view, name='guidance'),
    path('<str:zone_id>/', views.zone_detail_view, name='zone_detail_short'),
    path('api/status/', views.api_zones_status, name='api_status'),
    path('api/ping/', views.api_location_ping, name='api_ping'),
    path('api/telemetry/ping/', views.api_location_ping, name='api_telemetry_ping'),
]
