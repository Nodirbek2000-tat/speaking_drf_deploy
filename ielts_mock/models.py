from django.db import models
from django.conf import settings


class IELTSQuestion(models.Model):
    PART_CHOICES = [(1, 'Part 1'), (2, 'Part 2 - Cue Card'), (3, 'Part 3')]

    part = models.PositiveSmallIntegerField(choices=PART_CHOICES)
    question = models.TextField()

    # Part 1 uchun: birinchi savol (ism/joy so'rash)
    is_intro = models.BooleanField(
        default=False,
        help_text="Part 1 da birinchi savol sifatida ishlatiladi. "
                  "Masalan: 'Can you tell me your name and where you're from?'"
    )

    # Part 2 uchun
    cue_card_points = models.JSONField(
        null=True, blank=True,
        help_text='Part 2 uchun — ["Talk about...", "You should say:", "• point1", "• point2"]'
    )

    # Part 3 uchun: qaysi Part 2 ga bog'liq
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
        ordering = ['part', '-is_intro', 'id']

    def __str__(self):
        intro_tag = ' [INTRO]' if self.is_intro else ''
        return f"Part {self.part}{intro_tag}: {self.question[:60]}"


class IELTSPart1Question(IELTSQuestion):
    """Proxy model — admin panelda Part 1 savollar alohida bo'lim"""
    class Meta:
        proxy = True
        verbose_name = 'IELTS Part 1 Savol'
        verbose_name_plural = '📋 IELTS Part 1 — Savollar'


class IELTSPart23Set(IELTSQuestion):
    """Proxy model — admin panelda Part 2+3 (Cue Card) alohida bo'lim"""
    class Meta:
        proxy = True
        verbose_name = 'IELTS Cue Card (Part 2+3)'
        verbose_name_plural = '🃏 IELTS Part 2+3 — Cue Cards'


class IELTSSession(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='ielts_sessions'
    )
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
