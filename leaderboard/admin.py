from django.contrib import admin
from .models import LeaderboardEntry


@admin.register(LeaderboardEntry)
class LeaderboardEntryAdmin(admin.ModelAdmin):
    list_display = ["rank", "user", "period", "chat_count", "practice_count", "total_score"]
    list_filter = ["period"]
