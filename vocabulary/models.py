from django.db import models
from django.conf import settings


class Word(models.Model):
    LEVEL_CHOICES = [
        ('A1', 'A1'), ('A2', 'A2'), ('B1', 'B1'),
        ('B2', 'B2'), ('C1', 'C1'), ('C2', 'C2'),
    ]

    word = models.CharField(max_length=100, unique=True)
    level = models.CharField(max_length=2, choices=LEVEL_CHOICES)
    definition = models.TextField()
    translation_uz = models.TextField(blank=True)
    examples = models.JSONField(default=list, help_text='3-5 ta akademik misol jumlalar')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Word'
        verbose_name_plural = 'Words'
        ordering = ['level', 'word']

    def __str__(self):
        return f"[{self.level}] {self.word}"


class UserWord(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='saved_words')
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name='saved_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'word')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user} saved {self.word.word}"
