"""
Django production settings for CourseCompass project.
"""

from .base import *

DEBUG = False

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=['localhost'])

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True

# HTTPS settings (uncomment when using HTTPS)
# SECURE_SSL_REDIRECT = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

# Production logging - less verbose
LOGGING['root']['level'] = 'WARNING'
LOGGING['loggers']['bot']['level'] = 'INFO'
LOGGING['loggers']['courses']['level'] = 'INFO'
