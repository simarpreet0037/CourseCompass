# Import from the appropriate settings module based on environment
import os

environment = os.getenv('DJANGO_ENV', 'development')

if environment == 'production':
    from .prod import *
else:
    from .dev import *
