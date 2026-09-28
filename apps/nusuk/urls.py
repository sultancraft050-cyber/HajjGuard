from django.urls import path
from . import views

app_name = 'nusuk'

urlpatterns = [
    path('card/', views.digital_card_view, name='digital_card'),
    path('card/api/', views.api_card_details, name='api_card_details'),
    path('api/ai/chat/', views.api_nusuk_ai_chat, name='api_nusuk_ai_chat'),
]
