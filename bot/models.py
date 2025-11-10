# S advisor/models.py
# -------------------------
from django.db import models

class Student(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    program = models.CharField(max_length=100)

class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    course_code = models.CharField(max_length=10)
    term = models.CharField(max_length=20)
    grade = models.CharField(max_length=5, null=True, blank=True)