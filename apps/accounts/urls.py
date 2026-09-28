from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('profile/', views.profile_view, name='profile'),
    path('pilgrim/', views.pilgrim_portal, name='pilgrim_portal'),
    path('demo-switch/<str:username>/', views.demo_switch_user, name='demo_switch'),
]
