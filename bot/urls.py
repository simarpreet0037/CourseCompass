from django.urls import path
from . import views

app_name = "bot"

urlpatterns = [
    path('', views.chat_page, name='chat_page'),
    path('send-message/', views.send_message, name='send_message'),
    path('clear-history/', views.clear_history, name='clear_history'),
]
