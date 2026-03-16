from django.db import models
from django.conf import settings


class CEFRMock(models.Model):
    """Bitta to'liq CEFR mock testi — Part 1.1 + 1.2 + 2 + 3"""
    title = models.CharField(max_length=200, blank=True, verbose_name='Nomi (ixtiyoriy)')

    # Part 1.1 — 3 shaxsiy savol
    p1_q1 = models.TextField(verbose_name='Part 1.1: Savol 1')
    p1_q2 = models.TextField(verbose_name='Part 1.1: Savol 2')
    p1_q3 = models.TextField(verbose_name='Part 1.1: Savol 3')

    # Part 1.2 — 2–3 savol, har birida 2 rasm
    p1_2_instruction = models.TextField(blank=True, verbose_name="Part 1.2: Ko'rsatma (umumiy)")
    p1_2_q1       = models.TextField(verbose_name='Part 1.2: Savol 1')
    p1_2_q1_img1  = models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 1: Rasm 1')
    p1_2_q1_img2  = models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 1: Rasm 2')
    p1_2_q2       = models.TextField(verbose_name='Part 1.2: Savol 2')
    p1_2_q2_img1  = models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 2: Rasm 1')
    p1_2_q2_img2  = models.ImageField(upload_to='cefr_mock/', verbose_name='Part 1.2 Savol 2: Rasm 2')
    p1_2_q3       = models.TextField(blank=True, verbose_name='Part 1.2: Savol 3 (ixtiyoriy)')
    p1_2_q3_img1  = models.ImageField(upload_to='cefr_mock/', null=True, blank=True, verbose_name='Part 1.2 Savol 3: Rasm 1 (ixtiyoriy)')
    p1_2_q3_img2  = models.ImageField(upload_to='cefr_mock/', null=True, blank=True, verbose_name='Part 1.2 Savol 3: Rasm 2 (ixtiyoriy)')

    # Part 2 — Cue Card
    p2_question    = models.TextField(verbose_name='Part 2: Cue Card mavzu')
    p2_instruction = models.TextField(blank=True, verbose_name="Part 2: Ko'rsatma")
    p2_image       = models.ImageField(upload_to='cefr_mock/', null=True, blank=True, verbose_name='Part 2: Rasm (ixtiyoriy)')

    # Part 3 — FOR / AGAINST
    p3_topic       = models.TextField(verbose_name='Part 3: Muhokama mavzusi')
    p3_for_q1      = models.TextField(verbose_name='Part 3 FOR: Savol 1')
    p3_for_q2      = models.TextField(blank=True, verbose_name='Part 3 FOR: Savol 2 (ixtiyoriy)')
    p3_for_q3      = models.TextField(blank=True, verbose_name='Part 3 FOR: Savol 3 (ixtiyoriy)')
    p3_against_q1  = models.TextField(verbose_name='Part 3 AGAINST: Savol 1')
    p3_against_q2  = models.TextField(blank=True, verbose_name='Part 3 AGAINST: Savol 2 (ixtiyoriy)')
    p3_against_q3  = models.TextField(blank=True, verbose_name='Part 3 AGAINST: Savol 3 (ixtiyoriy)')

    is_active  = models.BooleanField(default=True, verbose_name='Faol')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'CEFR Mock'
        verbose_name_plural = 'CEFR Mocklar'
        ordering = ['-created_at']

    def __str__(self):
        return self.title or f'CEFR Mock #{self.pk}'


class CEFRQuestion(models.Model):
    PART_CHOICES = [
        (1, 'Part 1 - General Questions'),
        (2, 'Part 2 - Image Description'),
        (3, 'Part 3 - Compare/Discuss Images'),
        (4, 'Part 4 - Discussion'),
    ]

    part = models.PositiveSmallIntegerField(choices=PART_CHOICES)
    question = models.TextField()
    image = models.ImageField(upload_to='cefr_images/', null=True, blank=True, help_text='Part 2 va 3 uchun rasm')
    extra_images = models.JSONField(null=True, blank=True, help_text='Part 3 uchun qo\'shimcha rasmlar URL ro\'yxati')
    instruction = models.TextField(blank=True, help_text='Foydalanuvchiga ko\'rsatma')
    telegram_file_id = models.CharField(max_length=200, blank=True, help_text='Bot uchun Telegram rasm file_id (1-rasm)')

    # Part 1.2 uchun 2-rasm
    image2 = models.ImageField(upload_to='cefr_images/', null=True, blank=True, help_text='Part 1.2 uchun 2-rasm')
    telegram_file_id2 = models.CharField(max_length=200, blank=True, help_text='Bot uchun 2-rasm Telegram file_id')

    # Part 1 uchun: qaysi sub-qism
    sub_part = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text='Part 1 uchun: 1=Part1.1 (3 savol), 2=Part1.2 (2-3 savol)'
    )

    # Part 3 uchun: FOR yoki AGAINST pozitsiya
    stance = models.CharField(
        max_length=10, null=True, blank=True,
        choices=[('FOR', 'For'), ('AGAINST', 'Against')],
        help_text='Part 3 uchun: FOR yoki AGAINST'
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'CEFR Question'
        verbose_name_plural = 'CEFR Questions'

    def __str__(self):
        sub_tag = f'.{self.sub_part}' if self.sub_part else ''
        stance_tag = f' [{self.stance}]' if self.stance else ''
        return f"Part {self.part}{sub_tag}{stance_tag}: {self.question[:60]}"


class CEFRPart1_1Question(CEFRQuestion):
    """Proxy — Part 1.1 shaxsiy savollar"""
    class Meta:
        proxy = True
        verbose_name = 'CEFR Part 1.1 Savol'
        verbose_name_plural = '📋 CEFR Part 1.1 — Shaxsiy savollar'


class CEFRPart1_2Question(CEFRQuestion):
    """Proxy — Part 1.2 (2 ta rasm bilan solishtirish)"""
    class Meta:
        proxy = True
        verbose_name = 'CEFR Part 1.2 Savol'
        verbose_name_plural = '🖼 CEFR Part 1.2 — Rasmli savollar (2 ta)'


class CEFRPart2Question(CEFRQuestion):
    """Proxy — Part 2 Cue Card"""
    class Meta:
        proxy = True
        verbose_name = 'CEFR Part 2 Savol'
        verbose_name_plural = '🃏 CEFR Part 2 — Cue Card'


class CEFRPart3Question(CEFRQuestion):
    """Proxy — Part 3 FOR/AGAINST"""
    class Meta:
        proxy = True
        verbose_name = 'CEFR Part 3 Savol'
        verbose_name_plural = '💬 CEFR Part 3 — FOR / AGAINST'


class CEFRSession(models.Model):
    LEVEL_CHOICES = [
        ('A1', 'A1 - Beginner'),
        ('A2', 'A2 - Elementary'),
        ('B1', 'B1 - Intermediate'),
        ('B2', 'B2 - Upper Intermediate'),
        ('C1', 'C1 - Advanced'),
        ('C2', 'C2 - Mastery'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='cefr_sessions')
    questions = models.ManyToManyField(CEFRQuestion, through='CEFRAnswer')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    score = models.PositiveSmallIntegerField(null=True, blank=True)  # 1-75
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES, null=True, blank=True)
    feedback = models.JSONField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        score = self.score or '—'
        level = self.level or '—'
        return f"{self.user} | Score {score} ({level})"

    @staticmethod
    def score_to_level(score):
        if score <= 14:
            return 'A1'
        elif score <= 34:
            return 'A2'
        elif score <= 50:
            return 'B1'
        elif score <= 65:
            return 'B2'
        elif score <= 75:
            return 'C1'
        return 'C2'


class CEFRAnswer(models.Model):
    session = models.ForeignKey(CEFRSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(CEFRQuestion, on_delete=models.CASCADE)
    transcript = models.TextField(blank=True)
    audio_url = models.CharField(max_length=500, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
