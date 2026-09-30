"""
URL configuration for hajjguard_core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
import zones.views
from groups import pwa_views
from accounts import push_views, guardian_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('i18n/', include('django.conf.urls.i18n')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('safety/', include('safety.urls', namespace='safety')),
    path('zones/', include('zones.urls', namespace='zones')),
    path('groups/', include('groups.urls', namespace='groups')),
    path('analytics/', include('analytics.urls', namespace='analytics')),
    path('nusuk/', include('nusuk.urls', namespace='nusuk')),
    path('api/telemetry/ping/', zones.views.api_location_ping, name='api_telemetry_ping'),
    path('app/', pwa_views.pwa_shell, name='pwa_shell'),
    path('manifest.webmanifest', pwa_views.manifest, name='manifest'),
    path('service-worker.js', pwa_views.service_worker, name='service_worker'),
    path('api/trip/current', pwa_views.current_trip, name='current_trip'),
    path('api/trip/location-sharing/status', pwa_views.sharing_status, name='sharing_status'),
    path('api/trip/location-sharing/enable', pwa_views.enable_sharing, name='enable_sharing'),
    path('api/trip/location-sharing/revoke', pwa_views.revoke_sharing, name='revoke_sharing'),
    path('api/push/subscribe', push_views.subscribe_push, name='push_subscribe_root'),
    path('api/push/subscribe/<int:subscription_id>', push_views.revoke_push, name='push_revoke_root'),
    path('api/guardian/relationships', guardian_views.relationships, name='guardian_relationships_root'),
    path('api/guardian/relationships/create', guardian_views.create_relationship, name='guardian_create_root'),
    path('api/guardian/relationships/<int:relationship_id>/approve', guardian_views.approve_relationship, name='guardian_approve_root'),
    path('api/groups/<int:group_id>/live-members/', pwa_views.live_members, name='live_members_root'),
    path('api/groups/<int:group_id>/messages/', pwa_views.messages, name='messages_root'),
    path('api/groups/<int:group_id>/messages/create/', pwa_views.create_message, name='create_message_root'),
    path('api/groups/<int:group_id>/messages/<int:message_id>/attachments/', pwa_views.upload_attachment),
    path('api/groups/<int:group_id>/messages/<int:message_id>/attachment/', pwa_views.attachment),
    path('api/groups/<int:group_id>/messages/<int:message_id>/moderate/', pwa_views.moderate_message),
    path('api/groups/<int:group_id>/geofences/', pwa_views.list_geofences, name='geofences_root'),
    path('api/groups/<int:group_id>/geofences/create/', pwa_views.create_geofence, name='create_geofence_root'),
    path('api/groups/<int:group_id>/members/<int:member_id>/ping/', pwa_views.phone_ping, name='phone_ping_root'),
    path('api/geofences/<int:geofence_id>/acknowledge/', pwa_views.acknowledge_geofence, name='geofence_ack_root'),
    path('', zones.views.landing_home, name='home'),
    path('home/', zones.views.landing_home, name='home_explicit'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

