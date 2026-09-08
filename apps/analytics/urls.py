from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('api/trigger-surge/', views.api_trigger_surge, name='api_trigger_surge'),
    path('api/reset-crowd/', views.api_reset_crowd, name='api_reset_crowd'),
    path('api/calculate-route/', views.api_calculate_route, name='api_calculate_route'),
]
