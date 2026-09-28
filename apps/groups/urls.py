from django.urls import path
from . import views

app_name = 'groups'

urlpatterns = [
    path('my-group/', views.my_group_view, name='my_group'),
    path('lost-pilgrim/', views.lost_pilgrim_lookup_view, name='lost_pilgrim'),
    path('api/join/', views.api_join_group, name='api_join_group'),
]
