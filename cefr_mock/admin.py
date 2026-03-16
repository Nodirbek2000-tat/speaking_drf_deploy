from django.contrib import admin
from .models import CEFRMock, CEFRSession, CEFRAnswer
from django.utils.html import format_html


# ─── CEFR Mock Admin (tabbed form) ────────────────────────────────────────────

@admin.register(CEFRMock)
class CEFRMockAdmin(admin.ModelAdmin):
    list_display  = ['__str__', 'preview', 'is_active', 'created_at']
    list_editable = ['is_active']
    list_display_links = ['__str__']
    change_form_template = 'admin/cefr_mock/mock_change_form.html'

    fieldsets = [
        ('Part 1.1 — Shaxsiy savollar', {
            'fields': ['p1_q1', 'p1_q2', 'p1_q3'],
            'classes': ['tab-part1_1'],
        }),
        ('Part 1.2 — Rasm solishtirish', {
            'fields': [
                'p1_2_instruction',
                'p1_2_q1', 'p1_2_q1_img1', 'p1_2_q1_img2',
                'p1_2_q2', 'p1_2_q2_img1', 'p1_2_q2_img2',
                'p1_2_q3', 'p1_2_q3_img1', 'p1_2_q3_img2',
            ],
            'classes': ['tab-part1_2'],
        }),
        ('Part 2 — Cue Card', {
            'fields': ['p2_question', 'p2_instruction', 'p2_image'],
            'classes': ['tab-part2'],
        }),
        ('Part 3 — FOR / AGAINST', {
            'fields': [
                'p3_topic',
                'p3_for_q1', 'p3_for_q2', 'p3_for_q3',
                'p3_against_q1', 'p3_against_q2', 'p3_against_q3',
            ],
            'classes': ['tab-part3'],
        }),
        ('Sozlamalar', {
            'fields': ['title', 'is_active'],
        }),
    ]

    def preview(self, obj):
        p1 = obj.p1_q1[:40] + '…' if len(obj.p1_q1) > 40 else obj.p1_q1
        return format_html('<span style="color:#666;font-size:12px;">{}</span>', p1)
    preview.short_description = 'Part 1.1 — birinchi savol'


# ─── Session Admin ────────────────────────────────────────────────────────────

class CEFRAnswerInline(admin.TabularInline):
    model = CEFRAnswer
    readonly_fields = ['question', 'transcript', 'duration_seconds', 'created_at']
    extra = 0
    can_delete = False
    max_num = 0


@admin.register(CEFRSession)
class CEFRSessionAdmin(admin.ModelAdmin):
    list_display  = ['user', 'score_display', 'level', 'is_completed', 'started_at']
    list_filter   = ['is_completed', 'level']
    search_fields = ['user__username', 'user__first_name']
    readonly_fields = ['started_at', 'ended_at', 'feedback', 'score', 'level', 'user', 'is_completed']
    inlines = [CEFRAnswerInline]

    def score_display(self, obj):
        if obj.score is not None:
            color = '#10b981' if obj.score >= 66 else '#f59e0b' if obj.score >= 51 else '#ef4444'
            return format_html(
                '<span style="color:{};font-weight:bold">{}/75</span>', color, obj.score
            )
        return '—'
    score_display.short_description = 'Ball'
