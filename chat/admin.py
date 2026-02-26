from django.contrib import admin
from .models import ChatRoom, Message, ChatRating, AIChat, AIChatMessage


class MessageInline(admin.TabularInline):
    model = Message
    readonly_fields = ["sender", "content", "created_at"]
    extra = 0
    can_delete = False


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ["id", "user1", "user2", "status", "message_count", "started_at", "ended_at"]
    list_filter = ["status", "started_at"]
    search_fields = ["user1__username", "user2__username"]
    readonly_fields = ["started_at"]
    inlines = [MessageInline]

    def message_count(self, obj):
        return obj.messages.count()
    message_count.short_description = "Messages"


@admin.register(ChatRating)
class ChatRatingAdmin(admin.ModelAdmin):
    list_display = ["rater", "rated_user", "rating", "room", "created_at"]
    list_filter = ["rating"]
    search_fields = ["rater__username", "rated_user__username"]


@admin.register(AIChat)
class AIChatAdmin(admin.ModelAdmin):
    list_display = ["user", "created_at", "ended_at", "message_count"]
    search_fields = ["user__username"]

    def message_count(self, obj):
        return obj.messages.count()
