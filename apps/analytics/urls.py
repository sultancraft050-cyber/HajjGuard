from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('risk-board/', views.risk_board_view, name='risk_board'),
    path('reports/', views.reports_view, name='reports'),
    path('routing-comparison/', views.routing_comparison_view, name='routing_comparison'),
    path('reports/export/density/', views.export_density_csv, name='export_density_csv'),
    path('reports/export/incidents/', views.export_incidents_csv, name='export_incidents_csv'),
    path('export/density/', views.export_density_csv, name='export_density_csv_alias'),
    path('export/incidents/', views.export_incidents_csv, name='export_incidents_csv_alias'),
    path('api/trigger-surge/', views.api_trigger_surge, name='api_trigger_surge'),
    path('api/reset-crowd/', views.api_reset_crowd, name='api_reset_crowd'),
    path('api/calculate-route/', views.api_calculate_route, name='api_calculate_route'),
]
