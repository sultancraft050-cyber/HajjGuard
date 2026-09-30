from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .push_views import subscribe_push, revoke_push
from .guardian_views import create_relationship, approve_relationship, relationships

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='/accounts/login/'), name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('pilgrim/', views.pilgrim_portal, name='pilgrim_portal'),
    path('api/push/subscribe/', subscribe_push, name='subscribe_push'),
    path('api/push/subscribe/<int:subscription_id>/', revoke_push, name='revoke_push'),
    path('api/guardian/relationships/', relationships, name='guardian_relationships'),
    path('api/guardian/relationships/create/', create_relationship, name='create_guardian_relationship'),
    path('api/guardian/relationships/<int:relationship_id>/approve/', approve_relationship, name='approve_guardian_relationship'),
]
