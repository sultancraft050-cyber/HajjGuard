from django.urls import re_path
from .consumers import GroupConsumer

websocket_urlpatterns = [
    re_path(r'^/?ws/groups/(?P<group_id>[0-9]+)/$', GroupConsumer.as_asgi()),
]
