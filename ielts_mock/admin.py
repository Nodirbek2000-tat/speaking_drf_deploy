from django.contrib import admin
from django.utils.html import format_html
from .models import IELTSQuestion, IELTSSession, IELTSAnswer


class Part3InlineAdmin(admin.TabularInline):
    """Part 2 sahifasida bog'liq Part 3 savollarini ko'rsatish"""
    model = IELTSQuestion
    fk_name = 'related_part2'
    extra = 2
    fields = ['question', 'is_active']
    verbose_name = "Part 3 — bog'liq savol"
    verbose_name_plural = "Part 3 — bog'liq savollar (ushbu Part 2 ga tegishli)"
    show_change_link = True

    def get_queryset(self, request):
        return super().get_queryset(request).filter(part=3)

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == 'question':
            field.widget.attrs.update({'style': 'width:500px'})
        return field


@admin.register(IELTSQuestion)
class IELTSQuestionAdmin(admin.ModelAdmin):
    list_display = ['part_badge', 'question_preview', 'related_part2_col', 'is_active', 'created_at']
    list_filter = ['part', 'is_active']
    list_editable = ['is_active']
    search_fields = ['question']
    ordering = ['part', 'created_at']

    def get_inlines(self, request, obj):
        # Part 2 savolga kirganda Part 3 inline ko'rinadi
        if obj and obj.part == 2:
            return [Part3InlineAdmin]
        return []

    def get_fields(self, request, obj=None):
        fields = ['part', 'question', 'cue_card_points', 'is_active']
        if obj and obj.part == 3:
            fields.insert(2, 'related_part2')
        return fields

    def part_badge(self, obj):
        cfg = {
            1: ('#6f42c1', 'Part 1'),
            2: ('#007bff', 'Part 2 — Cue Card'),
            3: ('#28a745', 'Part 3'),
        }
        color, label = cfg.get(obj.part, ('#6c757d', f'Part {obj.part}'))
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 8px;'
            'border-radius:10px;font-size:12px">{}</span>',
            color, label
        )
    part_badge.short_description = 'Qism'
    part_badge.admin_order_field = 'part'

    def question_preview(self, obj):
        return obj.question[:80] + ('...' if len(obj.question) > 80 else '')
    question_preview.short_description = "Savol"

    def related_part2_col(self, obj):
        if obj.part == 3 and obj.related_part2:
            return format_html(
                '<span style="color:#007bff;font-size:12px">🔗 {}</span>',
                obj.related_part2.question[:40]
            )
        return '—'
    related_part2_col.short_description = 'Bog\'liq Part 2'


class IELTSAnswerInline(admin.TabularInline):
    model = IELTSAnswer
    readonly_fields = ["question_text", "transcript", "created_at"]
    fields = ["question_text", "transcript", "created_at"]
    extra = 0
    can_delete = False

    def question_text(self, obj):
        return format_html(
            '<b>[Part {}]</b> {}',
            obj.question.part,
            obj.question.question[:80]
        )
    question_text.short_description = "Savol"


@admin.register(IELTSSession)
class IELTSSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "band_badge", "parts_summary", "is_completed", "started_at", "ended_at"]
    list_filter = ["is_completed", "started_at"]
    search_fields = ["user__username", "user__telegram_id"]
    readonly_fields = ["started_at", "ended_at", "sub_scores_display",
                       "strengths", "improvements", "mistakes", "recommendations"]
    inlines = [IELTSAnswerInline]
    ordering = ['-started_at']

    def band_badge(self, obj):
        if obj.overall_band:
            color = '#28a745' if obj.overall_band >= 6.5 else '#ffc107' if obj.overall_band >= 5 else '#dc3545'
            return format_html(
                '<b style="font-size:16px;color:{}">⭐ {}</b>',
                color, obj.overall_band
            )
        return '—'
    band_badge.short_description = 'Band'
    band_badge.admin_order_field = 'overall_band'

    def parts_summary(self, obj):
        count = obj.answers.count()
        return format_html('<span style="color:#6c757d">{} ta savol</span>', count)
    parts_summary.short_description = 'Savollar'

    def sub_scores_display(self, obj):
        if not obj.sub_scores:
            return '—'
        s = obj.sub_scores
        return format_html(
            '🗣 Fluency: <b>{}</b> | 📖 Lexical: <b>{}</b> | ✏️ Grammar: <b>{}</b> | 🔊 Pronunciation: <b>{}</b>',
            s.get('fluency', '—'), s.get('lexical', '—'),
            s.get('grammar', '—'), s.get('pronunciation', '—')
        )
    sub_scores_display.short_description = 'Qism ballari'
