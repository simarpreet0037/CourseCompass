"""
Django settings for CourseCompass project.

DEPRECATED: This file is kept for backward compatibility.
Settings are now split into CourseCompass/settings/ directory:
  - base.py: Common settings
  - dev.py: Development settings
  - prod.py: Production settings

Set DJANGO_ENV=production in your environment for production settings.
"""

# Import all settings from the new settings package
from CourseCompass.settings import *
