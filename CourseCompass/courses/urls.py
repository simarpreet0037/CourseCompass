from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.add_course, name='add_course'),
    #path('success/', views.course_success, name='course_success'),
    path('view/', views.view_courses, name='view_courses'),
]