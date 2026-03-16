"""
Celery tasks: premium expiry notifications
"""
import logging
import requests
from celery import shared_task
from django.conf import settings
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task
def send_premium_expiry_warnings():
    """
    Har kuni ishlaydi: premium_expires 3 kun qolgan foydalanuvchilarga
    Telegram orqali ogohlantirish yuboradi.
    """
    from users.models import User

    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        logger.warning('[premium_expiry] TELEGRAM_BOT_TOKEN topilmadi')
        return

    now = timezone.now()
    # 3 kun qolgan: bugun tugamagan, lekin 3 kundan keyin tugaydigan
    warn_start = now + timedelta(days=3)
    warn_end   = now + timedelta(days=4)

    users = User.objects.filter(
        is_premium=True,
        premium_expires__gte=warn_start,
        premium_expires__lt=warn_end,
        telegram_id__isnull=False,
    )

    sent = 0
    for user in users:
        exp_str = user.premium_expires.strftime('%d.%m.%Y')
        text = (
            "⏰ <b>Premium obunangiz tugayapti!</b>\n\n"
            f"📅 Tugash sanasi: <b>{exp_str}</b>\n\n"
            "Uzluksiz foydalanish uchun premium obunani yangilang. "
            "Yangilash uchun /premium buyrug'ini yuboring yoki "
            "botdagi <b>💎 Premium</b> tugmasini bosing.\n\n"
            "🙏 Speaking Bot jamoasi"
        )
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={
                    "chat_id": user.telegram_id,
                    "text": text,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            if resp.ok:
                sent += 1
            else:
                logger.warning(f"[premium_expiry] Telegram failed for {user.telegram_id}: {resp.text[:200]}")
        except Exception as e:
            logger.error(f"[premium_expiry] Error sending to {user.telegram_id}: {e}")

    logger.info(f"[premium_expiry] {sent}/{users.count()} foydalanuvchiga ogohlantirish yuborildi")
    return sent
