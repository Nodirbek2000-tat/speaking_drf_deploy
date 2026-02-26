import json
import os
import requests
from django.contrib import admin
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from .models import DailyReport, Broadcast


def _send_text(token, chat_id, text, keyboard=None):
    payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'HTML'}
    if keyboard:
        payload['reply_markup'] = keyboard
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=payload, timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


def _send_photo(token, chat_id, img_path, caption, keyboard=None):
    data = {'chat_id': str(chat_id), 'caption': caption, 'parse_mode': 'HTML'}
    if keyboard:
        data['reply_markup'] = json.dumps(keyboard)
    try:
        with open(img_path, 'rb') as f:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendPhoto",
                data=data, files={'photo': f}, timeout=15
            )
        return r.status_code == 200
    except Exception:
        return False


@admin.register(Broadcast)
class BroadcastAdmin(admin.ModelAdmin):
    list_display = ['title', 'status_badge', 'sent_count', 'created_by', 'created_at', 'sent_at']
    list_filter = ['is_sent', 'created_at']
    search_fields = ['title', 'message']
    readonly_fields = ['is_sent', 'sent_at', 'sent_count', 'created_by', 'image_preview']
    fields = [
        'title', 'message', 'image', 'image_preview',
        'link', 'button_text',
        'is_sent', 'sent_count', 'sent_at', 'created_by'
    ]
    actions = ['send_now']

    def status_badge(self, obj):
        if obj.is_sent:
            return format_html(
                '<span style="color:#28a745;font-weight:bold">✅ Yuborildi ({})</span>',
                obj.sent_count
            )
        return format_html('<span style="color:#ffc107;font-weight:bold">⏳ Kutmoqda</span>')
    status_badge.short_description = 'Holat'

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="max-height:150px;border-radius:6px"></a>',
                obj.image.url, obj.image.url
            )
        return '—'
    image_preview.short_description = "Rasm ko'rinishi"

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    @admin.action(description="📢 Hozir yuborish — barcha bot foydalanuvchilariga")
    def send_now(self, request, queryset):
        from users.models import BotActivity

        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            self.message_user(request, "❌ TELEGRAM_BOT_TOKEN sozlanmagan!", level='error')
            return

        for broadcast in queryset:
            if broadcast.is_sent:
                self.message_user(
                    request,
                    f"⚠️ '{broadcast.title}' allaqachon yuborilgan!",
                    level='warning'
                )
                continue

            telegram_ids = list(
                BotActivity.objects.values_list('telegram_id', flat=True).distinct()
            )
            if not telegram_ids:
                self.message_user(request, "⚠️ Bot foydalanuvchilari yo'q.", level='warning')
                continue

            kb = None
            if broadcast.link:
                btn = broadcast.button_text or "🔗 Batafsil"
                kb = {"inline_keyboard": [[{"text": btn, "url": broadcast.link}]]}

            sent = 0
            failed = 0
            for tg_id in telegram_ids:
                try:
                    if broadcast.image and broadcast.image.name:
                        img_path = os.path.join(settings.MEDIA_ROOT, broadcast.image.name)
                        if os.path.exists(img_path):
                            ok = _send_photo(token, tg_id, img_path, broadcast.message, kb)
                        else:
                            ok = _send_text(token, tg_id, broadcast.message, kb)
                    else:
                        ok = _send_text(token, tg_id, broadcast.message, kb)
                    if ok:
                        sent += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1

            broadcast.is_sent = True
            broadcast.sent_at = timezone.now()
            broadcast.sent_count = sent
            broadcast.save(update_fields=['is_sent', 'sent_at', 'sent_count'])
            self.message_user(
                request,
                f"✅ '{broadcast.title}' — {sent} ta yuborildi, {failed} ta xato."
            )


@admin.register(DailyReport)
class DailyReportAdmin(admin.ModelAdmin):
    list_display = ["user", "date", "chats_count", "ielts_score", "cefr_score", "sent_at"]
    list_filter = ["date"]
    search_fields = ["user__username"]
    readonly_fields = ["sent_at"]
