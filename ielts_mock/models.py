from django.db import models
from django.conf import settings


class IELTSQuestion(models.Model):
    PART_CHOICES = [(1, 'Part 1'), (2, 'Part 2 - Cue Card'), (3, 'Part 3')]

    part = models.PositiveSmallIntegerField(choices=PART_CHOICES)
    question = models.TextField()
    cue_card_points = models.JSONField(null=True, blank=True, help_text='Part 2 uchun - [point1, point2, ...]')
    related_part2 = models.ForeignKey(
        'self', null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='part3_follow_up',
        limit_choices_to={'part': 2},
        help_text='Part 3 uchun: qaysi Part 2 savoliga tegishli?'
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'IELTS Question'
        verbose_name_plural = 'IELTS Questions'

    def __str__(self):
        return f"Part {self.part}: {self.question[:60]}"


class IELTSSession(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ielts_sessions')
    questions = models.ManyToManyField(IELTSQuestion, through='IELTSAnswer')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    overall_band = models.FloatField(null=True, blank=True)
    sub_scores = models.JSONField(null=True, blank=True)
    strengths = models.JSONField(null=True, blank=True)
    improvements = models.JSONField(null=True, blank=True)
    mistakes = models.JSONField(null=True, blank=True)
    recommendations = models.JSONField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['-started_at']

    def __str__(self):
        band = self.overall_band or '—'
        return f"{self.user} | Band {band}"


class IELTSAnswer(models.Model):
    session = models.ForeignKey(IELTSSession, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(IELTSQuestion, on_delete=models.CASCADE)
    transcript = models.TextField(blank=True)
    audio_url = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
