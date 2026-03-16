from django.db import migrations


class Migration(migrations.Migration):
    """Reverted — fields moved to CEFR mock instead"""
    dependencies = [
        ('ielts_mock', '0005_add_proxy_models'),
    ]
    operations = []
