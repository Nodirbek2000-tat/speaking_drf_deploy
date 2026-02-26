import json
import requests as http_req
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.conf import settings
from django.utils import timezone
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import timedelta
from .models import User, Referral, BotActivity, UserTenseStats


# ─── Helper ───────────────────────────────────────────────────────────────────

def _send_telegram(chat_id, text, bot_token=None):
    token = bot_token or getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
    if not token:
        return False
    try:
        resp = http_req.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={'chat_id': int(chat_id), 'text': text, 'parse_mode': 'HTML'},
            timeout=10
        )
        return resp.status_code == 200
    except Exception as e:
        print(f"Telegram send error: {e}")
        return False


# ─── Bot Faoliyat Admin ────────────────────────────────────────────────────────

@admin.register(BotActivity)
class BotActivityAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'telegram_id_col', 'username_col',
        'activity_badge', 'score_col', 'created_at', 'msg_btn'
    ]
    list_filter = ['activity_type', 'created_at']
    search_fields = ['full_name', 'username', 'telegram_id']
    readonly_fields = ['telegram_id', 'full_name', 'username', 'activity_type', 'data_pretty', 'created_at']
    ordering = ['-created_at']
    list_per_page = 30
    date_hierarchy = 'created_at'
    actions = ['action_approve_premium', 'action_reject_premium']

    # ── Custom URLs ──

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                'send-message/',
                self.admin_site.admin_view(self.send_message_view),
                name='users_botactivity_send_message',
            ),
        ] + urls

    def send_message_view(self, request):
        if request.method == 'POST':
            tid = request.POST.get('telegram_id', '').strip()
            text = request.POST.get('text', '').strip()
            if tid and text:
                ok = _send_telegram(tid, text)
                if ok:
                    messages.success(request, f"✅ Xabar {tid} ga yuborildi!")
                else:
                    messages.error(request, "❌ Yuborishda xato! Token yoki ID ni tekshiring.")
            return redirect('../')

        context = dict(
            self.admin_site.each_context(request),
            telegram_id=request.GET.get('tid', ''),
            full_name=request.GET.get('name', ''),
            title='Telegram Xabar Yuborish',
        )
        return render(request, 'admin/users/send_message.html', context)

    # ── List columns ──

    def telegram_id_col(self, obj):
        return format_html('<code style="font-size:12px">{}</code>', obj.telegram_id)
    telegram_id_col.short_description = 'Telegram ID'
    telegram_id_col.admin_order_field = 'telegram_id'

    def username_col(self, obj):
        if obj.username:
            return format_html(
                '<a href="https://t.me/{0}" target="_blank" style="color:#17a2b8">@{0}</a>',
                obj.username
            )
        return '—'
    username_col.short_description = 'Username'

    def activity_badge(self, obj):
        cfg = {
            'start':           ('#20c997', '▶ Start'),
            'ielts_mock':      ('#28a745', '📝 IELTS'),
            'cefr_mock':       ('#007bff', '📊 CEFR'),
            'ai_chat':         ('#6f42c1', '🤖 AI Chat'),
            'word_lookup':     ('#fd7e14', '📚 Lug\'at'),
            'premium_request': ('#dc3545', '💎 Premium'),
        }
        color, label = cfg.get(obj.activity_type, ('#6c757d', obj.activity_type))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:12px;white-space:nowrap">{}</span>',
            color, label
        )
    activity_badge.short_description = 'Faoliyat'

    def score_col(self, obj):
        if obj.activity_type == 'ielts_mock':
            b = obj.data.get('band', obj.data.get('overall_band', '—'))
            return format_html('<b style="color:#28a745">Band: {}</b>', b)
        elif obj.activity_type == 'cefr_mock':
            s = obj.data.get('score', '—')
            l = obj.data.get('level', '')
            return format_html('<b style="color:#007bff">CEFR: {} ({})</b>', s, l)
        elif obj.activity_type == 'premium_request':
            plan = obj.data.get('plan', '—')
            price = obj.data.get('price', '')
            return format_html('<span style="color:#dc3545">{} {}</span>', plan, price)
        return '—'
    score_col.short_description = "Ball / Reja"

    def msg_btn(self, obj):
        url = (
            reverse('admin:users_botactivity_send_message')
            + f'?tid={obj.telegram_id}&name={obj.full_name}'
        )
        return format_html(
            '<a href="{}" style="background:#17a2b8;color:#fff;padding:3px 9px;'
            'border-radius:4px;font-size:12px;text-decoration:none;white-space:nowrap">'
            '✉ Xabar</a>',
            url
        )
    msg_btn.short_description = ''

    def data_pretty(self, obj):
        return format_html(
            '<pre style="font-size:12px;background:#1e1e2e;color:#cdd6f4;'
            'padding:10px;border-radius:6px;overflow:auto">{}</pre>',
            json.dumps(obj.data, ensure_ascii=False, indent=2)
        )
    data_pretty.short_description = "Ma'lumotlar"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    # ── Actions ──

    @admin.action(description="✅ Premium so'rovini TASDIQLASH + xabar yuborish")
    def action_approve_premium(self, request, queryset):
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        count = 0
        for act in queryset.filter(activity_type='premium_request'):
            plan = act.data.get('plan', '1 oy')
            ok = _send_telegram(
                act.telegram_id,
                f"🎉 <b>Tabriklaymiz!</b>\n\n"
                f"💎 <b>{plan} Premium</b> so'rovingiz tasdiqlandi!\n"
                f"⏳ Tez orada botda faollashtiriladi.\n\n"
                f"<i>Botga qayting va /start bosing.</i>",
                bot_token
            )
            if ok:
                count += 1
        self.message_user(request, f"✅ {count} ta foydalanuvchiga tasdiq xabari yuborildi.")

    @admin.action(description="❌ Premium so'rovini RAD ETISH + xabar yuborish")
    def action_reject_premium(self, request, queryset):
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        count = 0
        for act in queryset.filter(activity_type='premium_request'):
            ok = _send_telegram(
                act.telegram_id,
                "❌ <b>Premium so'rovingiz rad etildi.</b>\n\n"
                "To'lov cheki tasdiqlanmadi. Iltimos qayta urinib ko'ring "
                "yoki admin bilan bog'laning.",
                bot_token
            )
            if ok:
                count += 1
        self.message_user(request, f"❌ {count} ta foydalanuvchiga rad xabari yuborildi.")


# ─── Web User Admin ────────────────────────────────────────────────────────────

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username', 'full_name', 'email',
        'premium_badge', 'premium_expires', 'ielts_count', 'cefr_count',
        'is_online_dot', 'created_at'
    ]
    list_filter = ['is_premium', 'is_online', 'is_staff', 'date_joined']
    search_fields = ['username', 'email', 'telegram_id']
    readonly_fields = ['referral_code', 'created_at', 'updated_at', 'last_seen']
    ordering = ['-created_at']

    fieldsets = (
        ("Asosiy", {"fields": ("username", "first_name", "last_name", "email", "password")}),
        ("Profil", {"fields": ("telegram_id", "avatar", "bio", "native_language", "target_level")}),
        ("💎 Premium", {"fields": ("is_premium", "premium_expires", "referral_code", "referred_by")}),
        ("📊 Statistika", {"fields": ("chat_count", "practice_count", "ielts_count", "cefr_count", "free_searches_used")}),
        ("🌐 Online", {"fields": ("is_online", "last_seen", "searching_partner")}),
        ("🔧 Tizim", {"fields": ("is_staff", "is_active", "is_superuser", "groups", "user_permissions", "date_joined", "created_at", "updated_at")}),
    )
    actions = ['grant_1_month', 'grant_3_months', 'grant_1_year', 'revoke_premium', 'send_mass_message']

    # ── Custom URLs ──

    def get_urls(self):
        urls = super().get_urls()
        return [
            path(
                'broadcast/',
                self.admin_site.admin_view(self.broadcast_view),
                name='users_user_broadcast',
            ),
        ] + urls

    def broadcast_view(self, request):
        sent = failed = 0
        done = False
        if request.method == 'POST':
            text = request.POST.get('text', '').strip()
            if text:
                tg_users = User.objects.filter(
                    telegram_id__isnull=False
                ).values_list('telegram_id', flat=True)
                for tid in tg_users:
                    ok = _send_telegram(tid, text)
                    if ok:
                        sent += 1
                    else:
                        failed += 1
                done = True
                if sent:
                    messages.success(request, f"✅ {sent} ta foydalanuvchiga xabar yuborildi.")
                if failed:
                    messages.warning(request, f"⚠️ {failed} ta foydalanuvchiga yubormadi (bloklangan yoki xato).")
        context = dict(
            self.admin_site.each_context(request),
            title='📢 Broadcast — Mass Message',
            sent=sent,
            failed=failed,
            done=done,
        )
        return render(request, 'admin/users/broadcast.html', context)

    @admin.action(description="📢 Broadcast — hammaga xabar yuborish")
    def send_mass_message(self, request, queryset):
        from django.http import HttpResponseRedirect
        return HttpResponseRedirect(reverse('admin:users_user_broadcast'))

    def full_name(self, obj):
        return f"{obj.first_name} {obj.last_name}".strip() or "—"
    full_name.short_description = "Ismi"

    def premium_badge(self, obj):
        if obj.is_premium:
            return format_html('<span style="color:#ffd700;font-weight:bold">💎 Premium</span>')
        return format_html('<span style="color:#6c757d">Bepul</span>')
    premium_badge.short_description = "Status"
    premium_badge.admin_order_field = 'is_premium'

    def is_online_dot(self, obj):
        color = '#28a745' if obj.is_online else '#6c757d'
        label = 'Online' if obj.is_online else 'Offline'
        return format_html(
            '<span style="display:inline-block;width:8px;height:8px;border-radius:50%;'
            'background:{};margin-right:5px"></span>{}',
            color, label
        )
    is_online_dot.short_description = "Holat"

    def _grant(self, queryset, days):
        for user in queryset:
            user.is_premium = True
            user.premium_expires = timezone.now() + timedelta(days=days)
            user.save(update_fields=["is_premium", "premium_expires"])

    @admin.action(description="💎 1 oylik premium berish")
    def grant_1_month(self, request, queryset):
        self._grant(queryset, 30)
        self.message_user(request, f"✅ {queryset.count()} userga 1 oylik premium berildi.")

    @admin.action(description="💎 3 oylik premium berish")
    def grant_3_months(self, request, queryset):
        self._grant(queryset, 90)
        self.message_user(request, f"✅ {queryset.count()} userga 3 oylik premium berildi.")

    @admin.action(description="💎 1 yillik premium berish")
    def grant_1_year(self, request, queryset):
        self._grant(queryset, 365)
        self.message_user(request, f"✅ {queryset.count()} userga 1 yillik premium berildi.")

    @admin.action(description="🚫 Premiumni bekor qilish")
    def revoke_premium(self, request, queryset):
        queryset.update(is_premium=False, premium_expires=None)
        self.message_user(request, "✅ Premium bekor qilindi.")


@admin.register(UserTenseStats)
class UserTenseStatsAdmin(admin.ModelAdmin):
    list_display = ['telegram_id', 'date', 'tense_badge', 'usage_count', 'correct_count', 'accuracy_bar']
    list_filter = ['tense_name', 'date']
    search_fields = ['telegram_id']
    ordering = ['-date', 'tense_name']
    date_hierarchy = 'date'
    list_per_page = 50

    def tense_badge(self, obj):
        colors = {
            'present_simple': '#28a745',
            'past_simple': '#007bff',
            'future_simple': '#6f42c1',
            'present_perfect': '#fd7e14',
            'present_continuous': '#17a2b8',
            'past_perfect': '#dc3545',
            'conditional': '#6c757d',
        }
        labels = {
            'present_simple': 'Present Simple',
            'past_simple': 'Past Simple',
            'future_simple': 'Future',
            'present_perfect': 'Pres. Perfect',
            'present_continuous': 'Pres. Continuous',
            'past_perfect': 'Past Perfect',
            'conditional': 'Conditional',
        }
        color = colors.get(obj.tense_name, '#6c757d')
        label = labels.get(obj.tense_name, obj.tense_name)
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;border-radius:10px;font-size:12px">{}</span>',
            color, label
        )
    tense_badge.short_description = 'Zamon'

    def accuracy_bar(self, obj):
        acc = obj.accuracy or 0
        color = '#28a745' if acc >= 70 else '#ffc107' if acc >= 40 else '#dc3545'
        filled = round(acc / 10)
        bar = '█' * filled + '░' * (10 - filled)
        return format_html(
            '<span style="font-family:monospace;color:{}">{}</span> <b style="color:{}">{:.0f}%</b>',
            color, bar, color, acc
        )
    accuracy_bar.short_description = 'Aniqlik'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = ["referrer", "referred", "premium_granted", "created_at"]
    list_filter = ["premium_granted"]
    search_fields = ["referrer__username", "referred__username"]
