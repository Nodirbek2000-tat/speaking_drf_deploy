from django.contrib import admin
from .models import CEFRQuestion, CEFRSession, CEFRAnswer


@admin.register(CEFRQuestion)
class CEFRQuestionAdmin(admin.ModelAdmin):
    list_display = ["part", "question_preview", "has_image", "has_bot_image", "is_active", "created_at"]
    list_filter = ["part", "is_active"]
    list_editable = ["is_active"]
    search_fields = ["question"]
    fields = ["part", "question", "instruction", "image", "telegram_file_id", "extra_images", "is_active"]

    def question_preview(self, obj):
        return obj.question[:80]

    def has_image(self, obj):
        return bool(obj.image)
    has_image.boolean = True
    has_image.short_description = "Web rasm"

    def has_bot_image(self, obj):
        return bool(obj.telegram_file_id)
    has_bot_image.boolean = True
    has_bot_image.short_description = "Bot file_id"


class CEFRAnswerInline(admin.TabularInline):
    model = CEFRAnswer
    readonly_fields = ["question", "transcript", "duration_seconds", "created_at"]
    extra = 0
    can_delete = False


@admin.register(CEFRSession)
class CEFRSessionAdmin(admin.ModelAdmin):
    list_display = ["user", "score", "level", "is_completed", "started_at"]
    list_filter = ["is_completed", "level"]
    search_fields = ["user__username"]
    readonly_fields = ["started_at", "ended_at", "feedback"]
    inlines = [CEFRAnswerInline]
