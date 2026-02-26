from django.db import models
from django.conf import settings


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
    telegram_file_id = models.CharField(max_length=200, blank=True, help_text='Bot uchun Telegram rasm file_id (Part 2/3)')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'CEFR Question'
        verbose_name_plural = 'CEFR Questions'

    def __str__(self):
        return f"Part {self.part}: {self.question[:60]}"


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
