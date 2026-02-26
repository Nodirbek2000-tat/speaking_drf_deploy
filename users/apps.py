from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'users'

    def ready(self):
        self._patch_admin_index()

    def _patch_admin_index(self):
        from django.contrib import admin
        from django.utils import timezone

        original_index = admin.site.__class__.index

        def custom_index(self_site, request, extra_context=None):
            try:
                from users.models import User, BotActivity
                from vocabulary.models import Word
                from premium.models import PremiumPurchase
                from datetime import timedelta

                now = timezone.now()
                today = now.date()
                in_3_days = now + timedelta(days=3)

                extra_context = extra_context or {}
                extra_context.update({
                    # ── Stat karta raqamlari ──
                    'total_users': BotActivity.objects.values('telegram_id').distinct().count(),
                    'premium_users': User.objects.filter(is_premium=True).count(),
                    'today_active': BotActivity.objects.filter(
                        created_at__date=today
                    ).values('telegram_id').distinct().count(),
                    'total_ielts': BotActivity.objects.filter(activity_type='ielts_mock').count(),
                    'total_cefr': BotActivity.objects.filter(activity_type='cefr_mock').count(),
                    'total_words': Word.objects.count(),

                    # ── Pending premium so'rovlari ──
                    'pending_premium': PremiumPurchase.objects.filter(
                        status='pending'
                    ).select_related('user', 'plan').order_by('-created_at')[:5],
                    'pending_premium_count': PremiumPurchase.objects.filter(status='pending').count(),

                    # ── Premium muddati tugayapti (3 kun ichida) ──
                    'expiring_soon': User.objects.filter(
                        is_premium=True,
                        premium_expires__lte=in_3_days,
                        premium_expires__gte=now,
                    ).order_by('premium_expires')[:10],

                    # ── So'nggi faoliyatlar ──
                    'recent_activities': BotActivity.objects.select_related().all()[:15],

                    # ── IELTS mock natijalari ──
                    'recent_ielts': BotActivity.objects.filter(
                        activity_type='ielts_mock'
                    ).order_by('-created_at')[:8],

                    # ── CEFR mock natijalari ──
                    'recent_cefr': BotActivity.objects.filter(
                        activity_type='cefr_mock'
                    ).order_by('-created_at')[:8],
                })
            except Exception as e:
                print(f"Dashboard context error: {e}")
            return original_index(self_site, request, extra_context)

        admin.site.__class__.index = custom_index
