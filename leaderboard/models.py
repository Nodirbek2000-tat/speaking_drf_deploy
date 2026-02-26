from django.db import models
from django.conf import settings


class LeaderboardEntry(models.Model):
    PERIOD_CHOICES = [('weekly', 'Weekly'), ('monthly', 'Monthly'), ('alltime', 'All Time')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaderboard_entries')
    period = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    chat_count = models.PositiveIntegerField(default=0)
    practice_count = models.PositiveIntegerField(default=0)
    total_score = models.PositiveIntegerField(default=0)
    rank = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'period')
        ordering = ['rank']

    def __str__(self):
        return f"#{self.rank} {self.user} ({self.period})"
