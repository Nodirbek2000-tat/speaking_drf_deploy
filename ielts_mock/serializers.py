from rest_framework import serializers
from .models import IELTSQuestion, IELTSSession, IELTSAnswer


class IELTSQuestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = IELTSQuestion
        fields = ["id", "part", "question", "cue_card_points"]


class IELTSAnswerSerializer(serializers.ModelSerializer):
    question = IELTSQuestionSerializer(read_only=True)

    class Meta:
        model = IELTSAnswer
        fields = ["id", "question", "transcript", "created_at"]


class IELTSSessionSerializer(serializers.ModelSerializer):
    answers = IELTSAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = IELTSSession
        fields = [
            "id", "started_at", "ended_at", "overall_band",
            "sub_scores", "strengths", "improvements",
            "mistakes", "recommendations", "is_completed", "answers",
        ]
