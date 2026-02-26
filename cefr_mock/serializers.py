from rest_framework import serializers
from .models import CEFRQuestion, CEFRSession, CEFRAnswer


class CEFRQuestionSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = CEFRQuestion
        fields = ["id", "part", "question", "image_url", "extra_images", "instruction"]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get("request")
            return request.build_absolute_uri(obj.image.url) if request else obj.image.url
        return None


class CEFRAnswerSerializer(serializers.ModelSerializer):
    question = CEFRQuestionSerializer(read_only=True)

    class Meta:
        model = CEFRAnswer
        fields = ["id", "question", "transcript", "duration_seconds", "created_at"]


class CEFRSessionSerializer(serializers.ModelSerializer):
    answers = CEFRAnswerSerializer(many=True, read_only=True)

    class Meta:
        model = CEFRSession
        fields = [
            "id", "started_at", "ended_at", "score", "level",
            "feedback", "is_completed", "answers",
        ]
