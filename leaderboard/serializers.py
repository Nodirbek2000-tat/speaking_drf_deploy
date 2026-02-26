from rest_framework import serializers
from users.models import User


class LeaderboardUserSerializer(serializers.ModelSerializer):
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "username", "avatar", "chat_count", "practice_count",
                  "ielts_count", "cefr_count", "avg_rating", "is_premium"]

    def get_avg_rating(self, obj):
        ratings = obj.received_ratings.all()
        if not ratings.exists():
            return None
        return round(sum(r.rating for r in ratings) / ratings.count(), 1)
