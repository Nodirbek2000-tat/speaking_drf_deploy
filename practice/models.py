from django.db import models
from django.conf import settings


class PracticeCategory(models.Model):
    CATEGORY_TYPE_CHOICES = [('academic', 'Academic Speaking'), ('daily', 'Daily Speaking')]

    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=10, default='📚')
    order = models.PositiveSmallIntegerField(default=0)
    category_type = models.CharField(max_length=10, choices=CATEGORY_TYPE_CHOICES, default='daily')

    class Meta:
        verbose_name = 'Practice Category'
        verbose_name_plural = 'Practice Categories'
        ordering = ['order']

    def __str__(self):
        return self.name


class PracticeScenario(models.Model):
    DIFFICULTY_CHOICES = [('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')]

    category = models.ForeignKey(PracticeCategory, on_delete=models.CASCADE, related_name='scenarios')
    title = models.CharField(max_length=200)
    description = models.TextField()
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    ai_prompt = models.TextField(help_text='AI uchun sistema prompt - faqat shu mavzuda gaplashsin')
    what_to_expect = models.TextField(blank=True, help_text='Bu sessiyada nima bo\'ladi - frontda ko\'rsatiladi')
    duration_minutes = models.PositiveSmallIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Practice Scenario'
        verbose_name_plural = 'Practice Scenarios'

    def __str__(self):
        return f"[{self.difficulty.upper()}] {self.title}"


class PracticeSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='practice_sessions')
    scenario = models.ForeignKey(PracticeScenario, on_delete=models.CASCADE, related_name='sessions')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)
    ai_feedback = models.JSONField(null=True, blank=True)
    overall_score = models.FloatField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user} - {self.scenario.title}"


class PracticeMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'AI')]
    session = models.ForeignKey(PracticeSession, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
