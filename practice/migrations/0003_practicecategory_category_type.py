from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('practice', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='practicecategory',
            name='category_type',
            field=models.CharField(
                choices=[('academic', 'Academic Speaking'), ('daily', 'Daily Speaking')],
                default='daily',
                max_length=10,
            ),
        ),
    ]
