from django.contrib import admin
from django.utils.html import format_html
from .models import IELTSQuestion, IELTSSession, IELTSAnswer


class Part3Inline(admin.TabularInline):
    """Part 2 sahifasida Part 3 savollarini birga ko'rish"""
    model = IELTSQuestion
    fk_name = 'related_part2'
    extra = 2
    fields = ['question', 'is_active']
    verbose_name = "Part 3 savol"
    verbose_name_plural = "Part 3 savollar (shu Part 2 ga bog'liq)"

    def get_queryset(self, request):
        return super().get_queryset(request).filter(part=3)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        return field

    def save_new_instance(self, parent, instance):
        instance.part = 3
        return instance


@admin.register(IELTSQuestion)
class IELTSQuestionAdmin(admin.ModelAdmin):
    list_display = ['part_badge', 'question_short', 'intro_badge', 'related_part2_display', 'is_active', 'created_at']
    list_filter = ['part', 'is_intro', 'is_active']
    list_editable = ['is_active']
    search_fields = ['question']
    ordering = ['part', '-is_intro', 'id']

    fieldsets = (
        ('Asosiy', {
            'fields': ('part', 'question', 'is_active')
        }),
        ('Part 1 sozlamalari', {
            'fields': ('is_intro',),
            'classes': ('collapse',),
            'description': '✅ Faqat Part 1 da ishlatiladi. "Can you tell me your name?" kabi kirish savoli.'
        }),
        ('Part 2 sozlamalari', {
            'fields': ('cue_card_points',),
            'classes': ('collapse',),
            'description': 'Part 2 uchun cue card punktlari. JSON format: ["Talk about a place", "You should say:", "• where it is", "• when you went"]'
        }),
        ('Part 3 sozlamalari', {
            'fields': ('related_part2',),
            'classes': ('collapse',),
            'description': '🔗 Part 3 savolini qaysi Part 2 ga bog\'lash. Part 3 savol qo\'shganda shu joyni to\'ldiring.'
        }),
    )

    # Part 2 sahifasida Part 3 ni birga ko'rsatish
    def get_inlines(self, request, obj=None):
        if obj and obj.part == 2:
            return [Part3Inline]
        return []

    def part_badge(self, obj):
        colors = {1: '#6366f1', 2: '#10b981', 3: '#f59e0b'}
        labels = {1: 'Part 1', 2: 'Part 2', 3: 'Part 3'}
        color = colors.get(obj.part, '#6b7280')
        label = labels.get(obj.part, f'Part {obj.part}')
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:12px;font-weight:bold">{}</span>',
            color, label
        )
    part_badge.short_description = "Part"

    def question_short(self, obj):
        return obj.question[:70] + ('...' if len(obj.question) > 70 else '')
    question_short.short_description = "Savol"

    def intro_badge(self, obj):
        if obj.is_intro:
            return format_html('<span style="color:#10b981;font-weight:bold">✅ INTRO</span>')
        return '—'
    intro_badge.short_description = "Intro"

    def related_part2_display(self, obj):
        if obj.related_part2:
            return format_html(
                '<span style="color:#10b981;font-size:12px">🔗 {}</span>',
                obj.related_part2.question[:40]
            )
        return '—'
    related_part2_display.short_description = "Part 2 bog'liq"

    def save_model(self, request, obj, form, change):
        # Part 3 saqlanganda related_part2 majburiy
        if obj.part == 3 and not obj.related_part2:
            # Warning chiqarish (lekin saqlash)
            pass
        super().save_model(request, obj, form, change)


class IELTSAnswerInline(admin.TabularInline):
    model = IELTSAnswer
    extra = 0
    readonly_fields = ['question', 'transcript', 'created_at']
    can_delete = False
    max_num = 0


@admin.register(IELTSSession)
class IELTSSessionAdmin(admin.ModelAdmin):
    list_display = ['user', 'overall_band_display', 'is_completed', 'started_at']
    list_filter = ['is_completed']
    search_fields = ['user__username', 'user__first_name']
    readonly_fields = [
        'user', 'started_at', 'ended_at', 'overall_band',
        'sub_scores', 'strengths', 'improvements',
        'mistakes', 'recommendations', 'is_completed'
    ]
    inlines = [IELTSAnswerInline]

    def overall_band_display(self, obj):
        if obj.overall_band:
            color = '#10b981' if obj.overall_band >= 7 else '#f59e0b' if obj.overall_band >= 5.5 else '#ef4444'
            return format_html(
                '<span style="color:{};font-weight:bold;font-size:16px">Band {}</span>',
                color, obj.overall_band
            )
        return '—'
    overall_band_display.short_description = "Band"