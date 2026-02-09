"""
Django development settings for CourseCompass project.
"""

from .base import *

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# More verbose logging in development
LOGGING['root']['level'] = 'DEBUG'
LOGGING['loggers']['bot']['level'] = 'DEBUG'
LOGGING['loggers']['courses']['level'] = 'DEBUG'

# Disable rate limiting in development
CHAT_RATE_LIMIT = 1000
