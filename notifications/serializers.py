from rest_framework import serializers
from .models import DailyReport


class DailyReportSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyReport
        fields = ["id", "date", "chats_count", "practice_count", "ielts_score",
                  "cefr_score", "words_learned", "report_data", "sent_at"]
