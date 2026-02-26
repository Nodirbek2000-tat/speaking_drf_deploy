import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    telegram_id = models.BigIntegerField(null=True, blank=True, unique=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    native_language = models.CharField(max_length=50, default='Uzbek')
    target_level = models.CharField(max_length=10, default='B2')

    is_premium = models.BooleanField(default=False)
    premium_expires = models.DateTimeField(null=True, blank=True)

    referral_code = models.CharField(max_length=12, unique=True, blank=True)
    referred_by = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL, related_name='referrals'
    )

    chat_count = models.PositiveIntegerField(default=0)
    practice_count = models.PositiveIntegerField(default=0)
    ielts_count = models.PositiveIntegerField(default=0)
    cefr_count = models.PositiveIntegerField(default=0)
    free_searches_used = models.PositiveIntegerField(default=0)

    GENDER_CHOICES = [('male', 'Male'), ('female', 'Female'), ('other', 'Other')]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    telegram_photo_url = models.URLField(blank=True, default='')

    is_online = models.BooleanField(default=False)
    last_seen = models.DateTimeField(null=True, blank=True)
    searching_partner = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.referral_code:
            self.referral_code = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)

    @property
    def has_premium_active(self):
        if not self.is_premium:
            return False
        if self.premium_expires and self.premium_expires < timezone.now():
            self.is_premium = False
            self.save(update_fields=['is_premium'])
            return False
        return True

    @property
    def can_search_partner(self):
        return self.has_premium_active or self.free_searches_used < 2


class BotActivity(models.Model):
    ACTIVITY_TYPES = [
        ('start', 'Bot Start'),
        ('ielts_mock', 'IELTS Mock'),
        ('cefr_mock', 'CEFR Mock'),
        ('word_lookup', 'Word Lookup'),
        ('ai_chat', 'AI Chat'),
        ('premium_request', "Premium So'rovi"),
    ]
    telegram_id = models.BigIntegerField(db_index=True)
    full_name = models.CharField(max_length=200)
    username = models.CharField(max_length=100, blank=True)
    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPES)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Bot Faoliyat'
        verbose_name_plural = 'Bot Faoliyatlari'

    def __str__(self):
        return f"{self.full_name} ({self.telegram_id}) — {self.activity_type}"


class UserTenseStats(models.Model):
    """Bot yoki web dan keluvchi kunlik tense aniqligi statistikasi"""
    telegram_id = models.BigIntegerField(db_index=True)
    date = models.DateField()
    tense_name = models.CharField(max_length=50)
    usage_count = models.PositiveIntegerField(default=0)
    correct_count = models.PositiveIntegerField(default=0)
    accuracy = models.FloatField(default=0.0)

    class Meta:
        unique_together = ['telegram_id', 'date', 'tense_name']
        verbose_name = 'Tense Statistika'
        verbose_name_plural = 'Tense Statistikalari'

    def __str__(self):
        return f"{self.telegram_id} | {self.date} | {self.tense_name} — {self.accuracy}%"


class Referral(models.Model):
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_referrals')
    referred = models.OneToOneField(User, on_delete=models.CASCADE, related_name='referral_record')
    premium_granted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Referral'
        verbose_name_plural = 'Referrals'

    def __str__(self):
        return f"{self.referrer} → {self.referred}"
