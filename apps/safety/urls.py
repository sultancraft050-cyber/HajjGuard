from django.urls import path
from . import views

app_name = 'safety'

urlpatterns = [
    path('dashboard/', views.operations_dashboard, name='operations_dashboard'),
    path('incidents/', views.incident_queue_view, name='incident_queue'),
    path('api/trigger-sos/', views.api_trigger_sos, name='api_trigger_sos'),
    path('api/assign-incident/', views.api_assign_incident, name='api_assign_incident'),
    path('api/resolve-incident/', views.api_resolve_incident, name='api_resolve_incident'),
    path('api/resolve/<int:incident_id>/', views.api_resolve_incident_by_id, name='api_resolve_by_id'),
    path('api/lookup-pilgrim/', views.api_lookup_pilgrim, name='api_lookup_pilgrim'),
    path('api/sync-haramain/', views.api_sync_haramain, name='api_sync_haramain'),
    path('api/live-weather/', views.api_live_weather, name='api_live_weather'),
    path('api/haram-sectional-status/', views.api_haram_sectional_status, name='api_haram_sectional_status'),
    path('api/simulate-section-gate-flow/', views.api_simulate_section_gate_flow, name='api_simulate_section_gate_flow'),
]
