import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.contrib.auth.models import User

try:
    if not User.objects.filter(username='admin').exists():
        User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
        print("✅ Superuser 'admin' created with password 'admin123'")
    else:
        print("ℹ️ Superuser 'admin' already exists.")
except Exception as e:
    print(f"❌ Error: {e}")
