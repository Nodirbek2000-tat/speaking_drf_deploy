from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('premium', '0004_add_price_uzs'),
    ]

    operations = [
        migrations.AddField(
            model_name='premiumpurchase',
            name='receipt_file_id',
            field=models.TextField(blank=True, default='', help_text="Telegram file_id (bot orqali yuborilgan chek)"),
        ),
    ]
