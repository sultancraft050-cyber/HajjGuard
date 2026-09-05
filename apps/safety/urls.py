from django.urls import path
from . import views

app_name = 'safety'

urlpatterns = [
    path('dashboard/', views.operations_dashboard, name='operations_dashboard'),
    path('api/trigger-sos/', views.api_trigger_sos, name='api_trigger_sos'),
    path('api/resolve/<int:incident_id>/', views.api_resolve_incident, name='api_resolve_incident'),
    path('api/lookup-pilgrim/', views.api_lookup_pilgrim, name='api_lookup_pilgrim'),
]
