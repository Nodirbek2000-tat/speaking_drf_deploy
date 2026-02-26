from rest_framework import serializers
from .models import PracticeCategory, PracticeScenario, PracticeSession, PracticeMessage


class PracticeMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PracticeMessage
        fields = ["id", "role", "content", "created_at"]


class PracticeScenarioSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    category_icon = serializers.CharField(source="category.icon", read_only=True)

    class Meta:
        model = PracticeScenario
        fields = [
            "id", "category", "category_name", "category_icon",
            "title", "description", "difficulty",
            "what_to_expect", "duration_minutes", "is_active",
        ]


class PracticeCategorySerializer(serializers.ModelSerializer):
    scenarios = PracticeScenarioSerializer(many=True, read_only=True)

    class Meta:
        model = PracticeCategory
        fields = ["id", "name", "icon", "order", "category_type", "scenarios"]


class PracticeSessionSerializer(serializers.ModelSerializer):
    scenario = PracticeScenarioSerializer(read_only=True)
    messages = PracticeMessageSerializer(many=True, read_only=True)

    class Meta:
        model = PracticeSession
        fields = [
            "id", "scenario", "started_at", "ended_at",
            "duration_seconds", "ai_feedback", "overall_score",
            "is_completed", "messages",
        ]
