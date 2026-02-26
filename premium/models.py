from django.db import models
from django.conf import settings


class PremiumPlan(models.Model):
    name = models.CharField(max_length=100)
    price_usd = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    price_uzs = models.PositiveIntegerField(default=0, help_text="Narx (so\'m)")
    duration_days = models.PositiveIntegerField()
    description = models.TextField()
    features = models.JSONField(default=list, help_text='Premium xususiyatlari ro\'yxati')
    is_active = models.BooleanField(default=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = 'Premium Plan'
        verbose_name_plural = 'Premium Plans'
        ordering = ['order']

    def __str__(self):
        return f"{self.name} - ${self.price_usd}"


class PremiumPurchase(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='purchases')
    plan = models.ForeignKey(PremiumPlan, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    telegram_username = models.CharField(max_length=100, blank=True)
    telegram_id = models.BigIntegerField(null=True, blank=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    receipt_image = models.ImageField(upload_to='receipts/', null=True, blank=True, help_text="To'lov cheki rasmi")
    receipt_file_id = models.TextField(blank=True, default='', help_text="Telegram file_id (bot orqali yuborilgan chek)")
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='confirmed_purchases'
    )

    class Meta:
        verbose_name = 'Premium Purchase'
        verbose_name_plural = 'Premium Purchases'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user} | {self.plan.name} | {self.status}"
