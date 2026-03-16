from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('cefr_mock', '0005_add_image2_proxy_models'),
    ]

    operations = [
        migrations.CreateModel(
            name='CEFRMock',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200, verbose_name='Nomi (ixtiyoriy)')),
                ('p1_q1', models.TextField(verbose_name='Part 1.1: Savol 1')),
                ('p1_q2', models.TextField(verbose_name='Part 1.1: Savol 2')),
                ('p1_q3', models.TextField(verbose_name='Part 1.1: Savol 3')),
                ('p1_2_instruction', models.TextField(blank=True, verbose_name="Part 1.2: Ko'rsatma (umumiy)")),
                ('p1_2_q1', models.TextField(verbose_name='Part 1.2: Savol 1')),
                ('p1_2_q1_img1', models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 1: Rasm 1')),
                ('p1_2_q1_img2', models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 1: Rasm 2')),
                ('p1_2_q2', models.TextField(verbose_name='Part 1.2: Savol 2')),
                ('p1_2_q2_img1', models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 2: Rasm 1')),
                ('p1_2_q2_img2', models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 2: Rasm 2')),
                ('p1_2_q3', models.TextField(blank=True, verbose_name='Part 1.2: Savol 3 (ixtiyoriy)')),
                ('p1_2_q3_img1', models.ImageField(blank=True, null=True, upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 3: Rasm 1 (ixtiyoriy)')),
                ('p1_2_q3_img2', models.ImageField(blank=True, null=True, upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 3: Rasm 2 (ixtiyoriy)')),
                ('p2_question', models.TextField(verbose_name='Part 2: Cue Card mavzu')),
                ('p2_instruction', models.TextField(blank=True, verbose_name="Part 2: Ko'rsatma")),
                ('p2_image', models.ImageField(blank=True, null=True, upload_to='cefr_mock/', verbose_name='Part 2: Rasm (ixtiyoriy)')),
                ('p3_topic', models.TextField(verbose_name='Part 3: Muhokama mavzusi')),
                ('p3_for_q1', models.TextField(verbose_name='Part 3 FOR: Savol 1')),
                ('p3_for_q2', models.TextField(blank=True, verbose_name='Part 3 FOR: Savol 2 (ixtiyoriy)')),
                ('p3_for_q3', models.TextField(blank=True, verbose_name='Part 3 FOR: Savol 3 (ixtiyoriy)')),
                ('p3_against_q1', models.TextField(verbose_name='Part 3 AGAINST: Savol 1')),
                ('p3_against_q2', models.TextField(blank=True, verbose_name='Part 3 AGAINST: Savol 2 (ixtiyoriy)')),
                ('p3_against_q3', models.TextField(blank=True, verbose_name='Part 3 AGAINST: Savol 3 (ixtiyoriy)')),
                ('is_active', models.BooleanField(default=True, verbose_name='Faol')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'CEFR Mock',
                'verbose_name_plural': 'CEFR Mocklar',
                'ordering': ['-created_at'],
            },
        ),
    ]
