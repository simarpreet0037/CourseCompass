from django.urls import path
from . import views

urlpatterns = [
    path('add/', views.add_course, name='add_course'),
    #path('success/', views.course_success, name='course_success'),
    path('view/', views.view_courses, name='view_courses'),
    path('courses/edit/<str:code>/', views.edit_course, name='edit_course'),
    path('delete/<str:code>/', views.delete_course, name='delete_course'),

]