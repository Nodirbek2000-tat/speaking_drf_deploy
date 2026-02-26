from rest_framework import serializers
from .models import Word, UserWord


class WordSerializer(serializers.ModelSerializer):
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Word
        fields = ["id", "word", "level", "definition", "translation_uz", "examples", "is_saved"]

    def get_is_saved(self, obj):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            return UserWord.objects.filter(user=request.user, word=obj).exists()
        return False


class UserWordSerializer(serializers.ModelSerializer):
    word = WordSerializer(read_only=True)

    class Meta:
        model = UserWord
        fields = ["id", "word", "saved_at"]
