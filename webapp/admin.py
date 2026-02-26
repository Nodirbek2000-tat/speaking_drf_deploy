from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from .models import AppSettings, PaymentCard, RequiredChannel, VoiceRoom, VoiceRating


@admin.register(AppSettings)
class AppSettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Bepul Limitlar', {
            'fields': ('free_calls_limit',),
            'description': 'Yangi foydalanuvchilar uchun bepul qo\'ng\'iroqlar soni',
        }),
        ('Referal Tizimi', {
            'fields': ('referrals_for_premium', 'referral_premium_days'),
        }),
        ('Web App', {
            'fields': ('web_app_url',),
        }),
    )

    def has_add_permission(self, request):
        return not AppSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def get_object(self, request, object_id, from_field=None):
        obj = AppSettings.get()
        return obj

    def changelist_view(self, request, extra_context=None):
        obj = AppSettings.get()
        return self.change_view(request, str(obj.pk), extra_context=extra_context)


@admin.register(PaymentCard)
class PaymentCardAdmin(admin.ModelAdmin):
    list_display = ('card_number', 'owner_name', 'bank_name', 'status_badge', 'created_at')
    list_display_links = ('card_number',)
    readonly_fields = ('created_at',)

    def status_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color:#10b981;font-weight:bold">✅ Aktiv</span>')
        return format_html('<span style="color:#6b7280">❌ Nofaol</span>')
    status_badge.short_description = 'Holat'

    def save_model(self, request, obj, form, change):
        if obj.is_active:
            PaymentCard.objects.exclude(pk=obj.pk).update(is_active=False)
        super().save_model(request, obj, form, change)


@admin.register(RequiredChannel)
class RequiredChannelAdmin(admin.ModelAdmin):
    list_display = ('channel_title', 'channel_username_link', 'is_active', 'bot_admin_status', 'created_at')
    list_editable = ('is_active',)
    readonly_fields = ('is_bot_admin', 'created_at')

    def channel_username_link(self, obj):
        return format_html(
            '<a href="{}" target="_blank">@{}</a>',
            obj.channel_link, obj.channel_username
        )
    channel_username_link.short_description = 'Username'

    def bot_admin_status(self, obj):
        if obj.is_bot_admin:
            return format_html('<span style="color:#10b981">✅ Admin</span>')
        return format_html('<span style="color:#ef4444">❌ Admin emas</span>')
    bot_admin_status.short_description = 'Bot holati'

    def save_model(self, request, obj, form, change):
        # Strip @ if present
        if obj.channel_username.startswith('@'):
            obj.channel_username = obj.channel_username[1:]
        super().save_model(request, obj, form, change)


@admin.register(VoiceRoom)
class VoiceRoomAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user1', 'user2_or_ai', 'partner_type', 'status_badge',
        'level', 'duration_display', 'started_at'
    )
    list_filter = ('partner_type', 'status', 'level')
    search_fields = ('user1__username', 'user2__username')
    readonly_fields = (
        'user1', 'user2', 'partner_type', 'status', 'gender_filter', 'level',
        'started_at', 'connected_at', 'ended_at', 'duration_seconds'
    )
    date_hierarchy = 'started_at'

    def user2_or_ai(self, obj):
        if obj.partner_type == 'ai':
            return '🤖 AI'
        return obj.user2 or '—'
    user2_or_ai.short_description = 'Partner'

    def status_badge(self, obj):
        colors = {'searching': '#f59e0b', 'active': '#10b981', 'ended': '#6b7280'}
        icons = {'searching': '🔍', 'active': '🟢', 'ended': '⭕'}
        color = colors.get(obj.status, '#6b7280')
        icon = icons.get(obj.status, '')
        return format_html(
            '<span style="color:{}">{} {}</span>',
            color, icon, obj.get_status_display()
        )
    status_badge.short_description = 'Holat'

    def duration_display(self, obj):
        if obj.duration_seconds:
            m, s = divmod(obj.duration_seconds, 60)
            return f"{m}:{s:02d}"
        return '—'
    duration_display.short_description = 'Davomiylik'


@admin.register(VoiceRating)
class VoiceRatingAdmin(admin.ModelAdmin):
    list_display = ('rater', 'rated_user', 'rating_stars', 'comment_preview', 'created_at')
    list_filter = ('rating',)
    readonly_fields = ('room', 'rater', 'rated_user', 'rating', 'comment', 'created_at')

    def rating_stars(self, obj):
        stars = '⭐' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span title="{}/5">{}</span>', obj.rating, stars)
    rating_stars.short_description = 'Baho'

    def comment_preview(self, obj):
        return (obj.comment[:60] + '...') if len(obj.comment) > 60 else obj.comment or '—'
    comment_preview.short_description = 'Izoh'
