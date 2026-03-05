from django.db import models
from django.conf import settings


class PracticeCategory(models.Model):
    CATEGORY_TYPE_CHOICES = [
        ('real_life', 'Real Life Situations'),
        ('academic', 'Academic Conversations'),
    ]

    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='🗣')
    description = models.TextField(blank=True, help_text="Kategoriya haqida qisqacha")
    order = models.PositiveSmallIntegerField(default=0)
    category_type = models.CharField(
        max_length=10,
        choices=CATEGORY_TYPE_CHOICES,
        default='real_life'
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Practice Category'
        verbose_name_plural = 'Practice Categories'
        ordering = ['order']

    def __str__(self):
        return f"{self.icon} {self.name}"


class PracticeScenario(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Easy'),
        ('medium', 'Medium'),
        ('hard', 'Hard'),
    ]

    category = models.ForeignKey(
        PracticeCategory,
        on_delete=models.CASCADE,
        related_name='scenarios'
    )
    title = models.CharField(max_length=200)
    description = models.TextField(help_text="Foydalanuvchiga ko'rsatiladigan qisqacha tavsif")

    # AI sozlamalari
    ai_prompt = models.TextField(
        help_text="AI uchun sistema prompt — faqat admin ko'radi, user ko'rmaydi"
    )
    ai_role = models.CharField(
        max_length=100,
        blank=True,
        default='',
        help_text="AI qanday rol o'ynaydi (masalan: Waiter, Doctor, Interviewer)"
    )

    # Foydalanuvchiga ko'rsatiladigan ma'lumotlar
    what_to_expect = models.TextField(
        blank=True,
        help_text="Bu sessiyada nima bo'ladi — har bir qatorga bitta narsa yozing"
    )

    difficulty = models.CharField(
        max_length=10,
        choices=DIFFICULTY_CHOICES,
        default='medium'
    )
    duration_minutes = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Practice Scenario'
        verbose_name_plural = 'Practice Scenarios'
        ordering = ['difficulty', 'title']

    def __str__(self):
        return f"[{self.difficulty.upper()}] {self.title}"

    def get_what_to_expect_list(self):
        """what_to_expect matnini bullet list ga aylantirish"""
        if not self.what_to_expect:
            return []
        return [line.strip() for line in self.what_to_expect.splitlines() if line.strip()]


class PracticeSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='practice_sessions'
    )
    scenario = models.ForeignKey(
        PracticeScenario,
        on_delete=models.CASCADE,
        related_name='sessions'
    )
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    # AI tahlil natijalari
    ai_feedback = models.JSONField(null=True, blank=True)
    overall_score = models.FloatField(null=True, blank=True)

    # Tenses statistikasi
    tense_stats = models.JSONField(
        null=True, blank=True,
        help_text="{'present_simple': {'total': 10, 'correct': 8, 'percent': 80}, ...}"
    )

    # Batafsil tahlil
    grammar_score = models.FloatField(null=True, blank=True)
    vocab_score = models.FloatField(null=True, blank=True)
    pronunciation_score = models.FloatField(null=True, blank=True)
    fluency_score = models.FloatField(null=True, blank=True)

    is_completed = models.BooleanField(default=False)
    analysis_done = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user} - {self.scenario.title} ({self.started_at.date()})"


class PracticeMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'AI')]

    session = models.ForeignKey(
        PracticeSession,
        on_delete=models.CASCADE,
        related_name='messages'
    )
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    audio_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"[{self.role}] {self.content[:50]}"