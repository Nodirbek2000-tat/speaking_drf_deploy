import requests
from django.contrib import admin
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from datetime import timedelta
from .models import PremiumPlan, PremiumPurchase


def _notify(chat_id, text):
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token or not chat_id:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': int(chat_id), 'text': text, 'parse_mode': 'HTML'},
            timeout=10
        )
        return r.status_code == 200
    except Exception:
        return False


@admin.register(PremiumPlan)
class PremiumPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "price_usd", "duration_days", "is_active", "order"]
    list_editable = ["is_active", "order", "price_usd"]
    ordering = ['order']


@admin.register(PremiumPurchase)
class PremiumPurchaseAdmin(admin.ModelAdmin):
    list_display = [
        'user_link', 'plan', 'status_badge', 'telegram_col',
        'receipt_thumb', 'created_at', 'quick_actions'
    ]
    list_filter = ['status', 'plan', 'created_at']
    search_fields = ['user__username', 'telegram_username', 'telegram_id']
    readonly_fields = ['created_at', 'confirmed_at', 'confirmed_by', 'receipt_preview', 'tg_receipt_preview']
    fields = [
        'user', 'plan', 'status',
        'telegram_username', 'telegram_id', 'amount_paid',
        'receipt_image', 'receipt_preview',
        'receipt_file_id', 'tg_receipt_preview',
        'note', 'created_at', 'confirmed_at', 'confirmed_by'
    ]
    actions = ['bulk_confirm', 'bulk_reject']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'

    # ── Custom URLs for one-click approve/reject ──

    def get_urls(self):
        return [
            path(
                '<int:pk>/confirm/',
                self.admin_site.admin_view(self.confirm_view),
                name='premium_purchase_confirm',
            ),
            path(
                '<int:pk>/reject/',
                self.admin_site.admin_view(self.reject_view),
                name='premium_purchase_reject',
            ),
            path(
                '<int:pk>/photo/',
                self.admin_site.admin_view(self.photo_view),
                name='premium_purchase_photo',
            ),
        ] + super().get_urls()

    def photo_view(self, request, pk):
        """Telegram file_id orqali chek rasmini admin brauzerida ochish"""
        import urllib.request as urlreq
        import json as _json
        from django.http import HttpResponseRedirect, HttpResponse
        purchase = get_object_or_404(PremiumPurchase, pk=pk)
        file_id = purchase.receipt_file_id
        if not file_id:
            return HttpResponse("No file_id", status=404)
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if not token:
            return HttpResponse("No bot token", status=500)
        try:
            resp = urlreq.urlopen(
                f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}",
                timeout=10
            )
            data = _json.loads(resp.read())
            file_path = data['result']['file_path']
            url = f"https://api.telegram.org/file/bot{token}/{file_path}"
            return HttpResponseRedirect(url)
        except Exception as e:
            return HttpResponse(f"Error: {e}", status=500)

    def confirm_view(self, request, pk):
        purchase = get_object_or_404(PremiumPurchase, pk=pk)
        if purchase.status == 'pending':
            purchase.status = 'confirmed'
            purchase.confirmed_at = timezone.now()
            purchase.confirmed_by = request.user
            purchase.save()
            # DRF userni ham yangilash
            user = purchase.user
            user.is_premium = True
            user.premium_expires = timezone.now() + timedelta(days=purchase.plan.duration_days)
            user.save(update_fields=["is_premium", "premium_expires"])
            # Telegram xabar
            _notify(
                purchase.telegram_id,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"💎 <b>{purchase.plan.name} Premium</b> faollashtirildi!\n"
                f"Endi cheksiz mock test topshiring va o'sing! 🚀\n\n"
                f"Botga qayting va /start bosing."
            )
            messages.success(request, f"✅ {purchase.user.username} ga premium tasdiqlandi va xabar yuborildi.")
        else:
            messages.warning(request, f"⚠️ Bu so'rov allaqachon {purchase.get_status_display()} holatida.")
        return redirect('../../')

    def reject_view(self, request, pk):
        purchase = get_object_or_404(PremiumPurchase, pk=pk)
        if purchase.status == 'pending':
            purchase.status = 'rejected'
            purchase.save()
            _notify(
                purchase.telegram_id,
                "❌ <b>Premium so'rovingiz rad etildi.</b>\n\n"
                "To'lov cheki tasdiqlanmadi. Iltimos to'g'ri chek yuboring "
                "yoki admin bilan bog'laning."
            )
            messages.warning(request, "❌ So'rov rad etildi va foydalanuvchiga xabar yuborildi.")
        return redirect('../../')

    # ── List columns ──

    def user_link(self, obj):
        return format_html('<b>{}</b>', obj.user.username)
    user_link.short_description = 'Foydalanuvchi'

    def status_badge(self, obj):
        cfg = {
            'pending':   ('#ffc107', '#000', '⏳ Kutmoqda'),
            'confirmed': ('#28a745', '#fff', '✅ Tasdiqlandi'),
            'rejected':  ('#dc3545', '#fff', '❌ Rad etildi'),
        }
        bg, fg, label = cfg.get(obj.status, ('#6c757d', '#fff', obj.status))
        return format_html(
            '<span style="background:{};color:{};padding:3px 10px;'
            'border-radius:10px;font-size:12px">{}</span>',
            bg, fg, label
        )
    status_badge.short_description = 'Holat'
    status_badge.admin_order_field = 'status'

    def telegram_col(self, obj):
        parts = []
        if obj.telegram_username:
            parts.append(f'@{obj.telegram_username}')
        if obj.telegram_id:
            parts.append(f'<code>{obj.telegram_id}</code>')
        return format_html(' '.join(parts)) if parts else '—'
    telegram_col.short_description = 'Telegram'

    def receipt_thumb(self, obj):
        if obj.receipt_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="height:45px;border-radius:4px;cursor:pointer" title="Ko\'rish"></a>',
                obj.receipt_image.url, obj.receipt_image.url
            )
        if obj.receipt_file_id:
            return format_html(
                '<a href="{}/photo/" target="_blank" '
                'style="background:#2563eb;color:#fff;padding:3px 8px;border-radius:4px;font-size:11px;text-decoration:none">'
                '📸 TG Chek</a>',
                obj.pk
            )
        return '—'
    receipt_thumb.short_description = 'Chek'

    def tg_receipt_preview(self, obj):
        if obj.receipt_file_id:
            return format_html(
                '<a href="{}/photo/" target="_blank" '
                'style="background:#2563eb;color:#fff;padding:6px 14px;border-radius:6px;'
                'font-size:13px;text-decoration:none;display:inline-block">'
                '📸 Telegram chekni ko\'rish</a>'
                '<br><small style="color:#888">file_id: {}</small>',
                obj.pk, obj.receipt_file_id[:30] + '...' if len(obj.receipt_file_id) > 30 else obj.receipt_file_id
            )
        return '— (fayl yo\'q)'
    tg_receipt_preview.short_description = "Telegram Chek"

    def receipt_preview(self, obj):
        if obj.receipt_image:
            return format_html(
                '<a href="{}" target="_blank">'
                '<img src="{}" style="max-width:450px;border-radius:8px"></a>',
                obj.receipt_image.url, obj.receipt_image.url
            )
        return '—'
    receipt_preview.short_description = "Chek rasmi (katta)"

    def quick_actions(self, obj):
        if obj.status == 'pending':
            return format_html(
                '<a href="{}/confirm/" style="background:#28a745;color:#fff;padding:3px 10px;'
                'border-radius:4px;font-size:12px;text-decoration:none;margin-right:4px">'
                '✅ Tasdiq</a>'
                '<a href="{}/reject/" style="background:#dc3545;color:#fff;padding:3px 10px;'
                'border-radius:4px;font-size:12px;text-decoration:none">'
                '❌ Rad</a>',
                obj.pk, obj.pk
            )
        return '—'
    quick_actions.short_description = 'Amal'

    # ── Bulk actions ──

    @admin.action(description="✅ Tanlangan so'rovlarni tasdiqlash + xabar")
    def bulk_confirm(self, request, queryset):
        count = 0
        for purchase in queryset.filter(status='pending'):
            purchase.status = 'confirmed'
            purchase.confirmed_at = timezone.now()
            purchase.confirmed_by = request.user
            purchase.save()
            user = purchase.user
            user.is_premium = True
            user.premium_expires = timezone.now() + timedelta(days=purchase.plan.duration_days)
            user.save(update_fields=["is_premium", "premium_expires"])
            _notify(purchase.telegram_id, f"🎉 <b>{purchase.plan.name} Premium</b> faollashtirildi! 💎")
            count += 1
        self.message_user(request, f"✅ {count} ta so'rov tasdiqlandi.")

    @admin.action(description="❌ Tanlangan so'rovlarni rad etish + xabar")
    def bulk_reject(self, request, queryset):
        count = 0
        for purchase in queryset.filter(status='pending'):
            purchase.status = 'rejected'
            purchase.save()
            _notify(purchase.telegram_id, "❌ Premium so'rovingiz rad etildi.")
            count += 1
        self.message_user(request, f"❌ {count} ta so'rov rad etildi.")
