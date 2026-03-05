from django.contrib import admin
from django.utils.html import format_html
from .models import PracticeCategory, PracticeScenario, PracticeSession, PracticeMessage


@admin.register(PracticeCategory)
class PracticeCategoryAdmin(admin.ModelAdmin):
    list_display = ['icon', 'name', 'category_type', 'scenario_count', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['category_type', 'is_active']
    search_fields = ['name']
    ordering = ['order']

    def scenario_count(self, obj):
        count = obj.scenarios.filter(is_active=True).count()
        return format_html('<b>{}</b> ta scenario', count)
    scenario_count.short_description = "Scenariolar"


class PracticeMessageInline(admin.TabularInline):
    model = PracticeMessage
    extra = 0
    readonly_fields = ['role', 'content', 'created_at']
    can_delete = False
    max_num = 0


@admin.register(PracticeScenario)
class PracticeScenarioAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'category', 'ai_role_display',
        'difficulty_badge', 'duration_minutes', 'is_active', 'created_at'
    ]
    list_filter = ['category__category_type', 'category', 'difficulty', 'is_active']
    search_fields = ['title', 'description', 'ai_role']
    list_editable = ['is_active']
    ordering = ['category__order', 'difficulty']

    fieldsets = (
        ('Asosiy ma\'lumotlar', {
            'fields': ('category', 'title', 'description', 'difficulty', 'duration_minutes', 'is_active')
        }),
        ('AI sozlamalari', {
            'fields': ('ai_role', 'ai_prompt'),
            'description': '⚠️ AI Prompt foydalanuvchiga ko\'rinmaydi. AI shu prompt asosida muloqot qiladi.'
        }),
        ('Foydalanuvchiga ko\'rsatish', {
            'fields': ('what_to_expect',),
            'description': 'Har bir qatorga bitta narsa yozing. Ular bullet list ko\'rinishida chiqadi.'
        }),
    )

    def ai_role_display(self, obj):
        if obj.ai_role:
            return format_html('<span style="color:#6366f1;font-weight:bold">🤖 {}</span>', obj.ai_role)
        return '—'
    ai_role_display.short_description = "AI Roli"

    def difficulty_badge(self, obj):
        colors = {'easy': '#10b981', 'medium': '#f59e0b', 'hard': '#ef4444'}
        labels = {'easy': 'Easy', 'medium': 'Medium', 'hard': 'Hard'}
        color = colors.get(obj.difficulty, '#6b7280')
        label = labels.get(obj.difficulty, obj.difficulty)
        return format_html(
            '<span style="background:{};color:white;padding:2px 8px;border-radius:4px;font-size:12px">{}</span>',
            color, label
        )
    difficulty_badge.short_description = "Darajasi"


@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'scenario', 'overall_score',
        'grammar_score', 'vocab_score',
        'duration_display', 'is_completed', 'analysis_done', 'started_at'
    ]
    list_filter = ['is_completed', 'analysis_done', 'scenario__category']
    search_fields = ['user__username', 'user__first_name', 'scenario__title']
    readonly_fields = [
        'user', 'scenario', 'started_at', 'ended_at',
        'duration_seconds', 'ai_feedback', 'tense_stats',
        'overall_score', 'grammar_score', 'vocab_score',
        'pronunciation_score', 'fluency_score',
        'is_completed', 'analysis_done'
    ]
    inlines = [PracticeMessageInline]

    def duration_display(self, obj):
        if obj.duration_seconds:
            m = obj.duration_seconds // 60
            s = obj.duration_seconds % 60
            return f"{m}:{s:02d}"
        return '—'
    duration_display.short_description = "Davomiyligi"