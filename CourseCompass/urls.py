from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='bot:chat_page', permanent=False)),
    path('admin/', admin.site.urls),
    path('courses/', include('courses.urls')),
    path('chat/', include('bot.urls')),
]
