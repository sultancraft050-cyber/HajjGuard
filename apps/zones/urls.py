from django.urls import path
from . import views

app_name = 'zones'

urlpatterns = [
    path('map/', views.live_map_view, name='live_map'),
    path('api/status/', views.api_zones_status, name='api_status'),
    path('api/ping/', views.api_location_ping, name='api_ping'),
]
