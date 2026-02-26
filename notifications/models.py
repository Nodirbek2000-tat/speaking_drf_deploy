from django.db import models
from django.conf import settings


class Broadcast(models.Model):
    title = models.CharField(max_length=200, help_text="Broadcast nomi (foydalanuvchiga ko'rinmaydi)")
    message = models.TextField(help_text="Yuborilinadigan xabar matni")
    image = models.ImageField(upload_to='broadcasts/', null=True, blank=True, help_text="Rasm (ixtiyoriy)")
    link = models.URLField(blank=True, help_text="Tugma linki (ixtiyoriy)")
    button_text = models.CharField(max_length=100, blank=True, default="🔗 Batafsil", help_text="Tugma matni")
    is_sent = models.BooleanField(default=False)
    sent_at = models.DateTimeField(null=True, blank=True)
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='broadcasts'
    )

    class Meta:
        verbose_name = 'Broadcast'
        verbose_name_plural = 'Broadcastlar'
        ordering = ['-created_at']

    def __str__(self):
        status = "✅ Yuborildi" if self.is_sent else "⏳ Kutmoqda"
        return f"{self.title} [{status}]"


class DailyReport(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='daily_reports')
    date = models.DateField()
    chats_count = models.PositiveIntegerField(default=0)
    practice_count = models.PositiveIntegerField(default=0)
    ielts_score = models.FloatField(null=True, blank=True)
    cefr_score = models.PositiveSmallIntegerField(null=True, blank=True)
    words_learned = models.PositiveIntegerField(default=0)
    report_data = models.JSONField(default=dict)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']

    def __str__(self):
        return f"{self.user} | {self.date}"
