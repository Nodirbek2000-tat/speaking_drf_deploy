"""
Django signallari: Admin panel orqali premium o'zgarganda Telegram notification
"""
import logging
import requests
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(pre_save, sender='users.User')
def track_premium_change(sender, instance, **kwargs):
    """Save old premium status before update"""
    if instance.pk:
        try:
            old = sender.objects.get(pk=instance.pk)
            instance._premium_was = old.is_premium
        except sender.DoesNotExist:
            instance._premium_was = False
    else:
        instance._premium_was = False


@receiver(post_save, sender='users.User')
def notify_premium_change(sender, instance, created, **kwargs):
    """Admin premium o'zgartirsa → Telegram notification yuborish"""
    if created:
        return

    old_premium = getattr(instance, '_premium_was', None)
    if old_premium is None or old_premium == instance.is_premium:
        return

    if not instance.telegram_id:
        return

    from django.conf import settings
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        return

    if instance.is_premium:
        exp_str = instance.premium_expires.strftime('%d.%m.%Y') if instance.premium_expires else '∞'
        text = (
            "🎉 <b>Tabriklaymiz! Premium faollashtirildi!</b>\n\n"
            "✅ Cheksiz IELTS va CEFR mock testlar\n"
            "✅ Cheksiz AI suhbat (ovozli xabarlar)\n"
            "✅ Cheksiz so'z qidirish\n"
            "✅ Batafsil tahlil va AI hisobotlar\n"
            "✅ My Progress (tense statistika)\n"
            "✅ Kunlik shaxsiy reja\n\n"
            f"📅 Muddat: <b>{exp_str}</b>\n\n"
            "Barcha imkoniyatlardan foydalaning! 💎"
        )
    else:
        text = (
            "ℹ️ <b>Premium obunangiz bekor qilindi.</b>\n\n"
            "Yana premium olish uchun /premium buyrug'ini yuboring."
        )

    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": instance.telegram_id,
                "text": text,
                "parse_mode": "HTML",
            },
            timeout=10,
        )
        if not resp.ok:
            logger.warning(f"[signal] Telegram notify failed: {resp.text[:200]}")
        else:
            logger.info(f"[signal] Premium change notified: {instance.telegram_id} → premium={instance.is_premium}")
    except Exception as e:
        logger.error(f"[signal] Telegram notify error: {e}")
