import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'linkedin_collector.settings')
application = get_wsgi_application()
