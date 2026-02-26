from django.db import models
from django.conf import settings


class AppSettings(models.Model):
    """Singleton — global app settings"""
    free_calls_limit = models.PositiveIntegerField(
        default=3,
        help_text="Yangi foydalanuvchilar uchun bepul qo'ng'iroqlar soni"
    )
    referrals_for_premium = models.PositiveIntegerField(
        default=3,
        help_text="Bepul premium olish uchun zarur referal soni"
    )
    referral_premium_days = models.PositiveIntegerField(
        default=30,
        help_text="Referal orqali beriladigan bepul premium kunlar soni"
    )
    web_app_url = models.URLField(
        blank=True,
        help_text="Telegram Web App URL (masalan: https://yourdomain.com/webapp/)"
    )

    class Meta:
        verbose_name = 'App Sozlamalari'
        verbose_name_plural = 'App Sozlamalari'

    def __str__(self):
        return "App Sozlamalari"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class PaymentCard(models.Model):
    card_number = models.CharField(
        max_length=25,
        help_text="Karta raqami (masalan: 8600 1234 5678 9012)"
    )
    owner_name = models.CharField(
        max_length=100,
        help_text="Karta egasining ismi"
    )
    bank_name = models.CharField(
        max_length=100,
        default='',
        blank=True,
        help_text="Bank nomi (masalan: Uzcard, Humo)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Faqat 1 ta karta aktiv bo'lishi kerak"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "To'lov Kartasi"
        verbose_name_plural = "To'lov Kartalari"

    def __str__(self):
        return f"{self.card_number} — {self.owner_name}"

    def save(self, *args, **kwargs):
        if self.is_active:
            PaymentCard.objects.exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)


class RequiredChannel(models.Model):
    channel_title = models.CharField(
        max_length=100,
        help_text="Kanal nomi (ko'rsatish uchun)"
    )
    channel_username = models.CharField(
        max_length=100,
        help_text="@username (@ belgisisiz ham bo'ladi)"
    )
    channel_link = models.URLField(
        help_text="t.me/username havolasi"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Bu kanalga obunani tekshirish"
    )
    is_bot_admin = models.BooleanField(
        default=False,
        editable=False,
        help_text="Bot kanalda admin ekanligi (avtomatik tekshiriladi)"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Majburiy Kanal"
        verbose_name_plural = "Majburiy Kanallar"

    def __str__(self):
        return f"{self.channel_title} (@{self.channel_username})"


class VoiceRoom(models.Model):
    STATUS_CHOICES = [
        ('searching', 'Qidirilmoqda'),
        ('active', 'Faol'),
        ('ended', 'Tugadi'),
    ]
    PARTNER_TYPE_CHOICES = [
        ('human', 'Inson'),
        ('ai', 'AI'),
    ]
    GENDER_CHOICES = [
        ('male', 'Erkak'),
        ('female', 'Ayol'),
        ('any', 'Har qanday'),
    ]
    LEVEL_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('any', 'Any Level'),
    ]

    user1 = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='voice_rooms_as_user1'
    )
    user2 = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='voice_rooms_as_user2'
    )
    partner_type = models.CharField(max_length=10, choices=PARTNER_TYPE_CHOICES, default='human')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='searching')
    gender_filter = models.CharField(max_length=10, choices=GENDER_CHOICES, default='any')
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default='any')
    started_at = models.DateTimeField(auto_now_add=True)
    connected_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    duration_seconds = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Ovozli Suhbat Xonasi"
        verbose_name_plural = "Ovozli Suhbat Xonalari"
        ordering = ['-started_at']

    def __str__(self):
        if self.partner_type == 'ai':
            return f"{self.user1} ↔ AI"
        return f"{self.user1} ↔ {self.user2 or 'Qidirilmoqda'}"

    def get_partner(self, user):
        """Get the other user in the room"""
        if self.user1 == user:
            return self.user2
        return self.user1


class VoiceRating(models.Model):
    room = models.ForeignKey(VoiceRoom, on_delete=models.CASCADE, related_name='ratings')
    rater = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='given_voice_ratings'
    )
    rated_user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='received_voice_ratings'
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Suhbat Baholash"
        verbose_name_plural = "Suhbat Baholashlar"
        unique_together = ('room', 'rater')

    def __str__(self):
        return f"{self.rater} → {self.rated_user or 'AI'}: {self.rating}/5"
