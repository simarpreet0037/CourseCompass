"""
Django production settings for CourseCompass project.
"""

from .base import *

DEBUG = False

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS",default=["localhost", "127.0.0.1"])
USE_HTTPS = env.bool("USE_HTTPS", default=False)
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS",default=[])
PUBLIC_HOST = env("PUBLIC_HOST", default=env("PUBLIC_IP", default="")).strip()

if PUBLIC_HOST:
    if PUBLIC_HOST not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(PUBLIC_HOST)
    http_origin = f"http://{PUBLIC_HOST}"
    if http_origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(http_origin)
    if USE_HTTPS:
        https_origin = f"https://{PUBLIC_HOST}"
        if https_origin not in CSRF_TRUSTED_ORIGINS:
            CSRF_TRUSTED_ORIGINS.append(https_origin)

# Security settings for production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# HTTPS settings
CSRF_COOKIE_SECURE = USE_HTTPS
SESSION_COOKIE_SECURE = USE_HTTPS

if USE_HTTPS:
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# Production logging - less verbose
LOGGING['root']['level'] = 'WARNING'
LOGGING['loggers']['bot']['level'] = 'INFO'
LOGGING['loggers']['courses']['level'] = 'INFO'
