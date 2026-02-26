from django.contrib import admin
from .models import PracticeCategory, PracticeScenario, PracticeSession, PracticeMessage


@admin.register(PracticeCategory)
class PracticeCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "icon", "order", "scenario_count"]
    list_editable = ["order"]

    def scenario_count(self, obj):
        return obj.scenarios.count()


class PracticeMessageInline(admin.TabularInline):
    model = PracticeMessage
    readonly_fields = ["role", "content", "created_at"]
    extra = 0
    can_delete = False


@admin.register(PracticeScenario)
class PracticeScenarioAdmin(admin.ModelAdmin):
    list_display = ["title", "category", "difficulty", "duration_minutes", "is_active"]
    list_filter = ["category", "difficulty", "is_active"]
    search_fields = ["title"]
    list_editable = ["is_active", "difficulty"]


@admin.register(PracticeSession)
class PracticeSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "scenario", "duration_seconds", "overall_score", "is_completed", "started_at"]
    list_filter = ["is_completed"]
    search_fields = ["user__username"]
    readonly_fields = ["started_at", "ended_at", "ai_feedback"]
    inlines = [PracticeMessageInline]
