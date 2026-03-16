from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cefr_mock', '0003_cefrquestion_telegram_file_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='cefrquestion',
            name='sub_part',
            field=models.PositiveSmallIntegerField(
                blank=True, null=True,
                help_text='Part 1 uchun: 1=Part1.1 (3 savol), 2=Part1.2 (2-3 savol)'
            ),
        ),
        migrations.AddField(
            model_name='cefrquestion',
            name='stance',
            field=models.CharField(
                blank=True, null=True, max_length=10,
                choices=[('FOR', 'For'), ('AGAINST', 'Against')],
                help_text='Part 3 uchun: FOR yoki AGAINST'
            ),
        ),
    ]
