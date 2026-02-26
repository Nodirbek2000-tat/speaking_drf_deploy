import json
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from openai import OpenAI
from .models import Word, UserWord
from .serializers import WordSerializer, UserWordSerializer

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class WordListView(generics.ListAPIView):
    serializer_class = WordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Word.objects.all()
        level = self.request.query_params.get("level")
        if level:
            qs = qs.filter(level=level)
        return qs

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class LookupWordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        word_text = request.data.get("word", "").strip().lower()
        if not word_text:
            return Response({"error": "Word required"}, status=400)

        existing = Word.objects.filter(word__iexact=word_text).first()
        if existing:
            return Response(WordSerializer(existing, context={"request": request}).data)

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an English dictionary and vocabulary expert."},
                {"role": "user", "content": f"""For the word "{word_text}", return JSON:
{{
  "word": "{word_text}",
  "level": "B2",
  "definition": "Clear English definition",
  "translation_uz": "O'zbekcha tarjima",
  "examples": [
    "Academic example sentence 1 using the word.",
    "Academic example sentence 2 using the word.",
    "Academic example sentence 3 using the word.",
    "Academic example sentence 4 using the word.",
    "Academic example sentence 5 using the word."
  ]
}}
Level must be one of: A1, A2, B1, B2, C1, C2"""}
            ],
            response_format={"type": "json_object"},
            max_tokens=600
        )
        data = json.loads(resp.choices[0].message.content)
        word_obj = Word.objects.create(
            word=data.get("word", word_text),
            level=data.get("level", "B1"),
            definition=data.get("definition", ""),
            translation_uz=data.get("translation_uz", ""),
            examples=data.get("examples", []),
        )
        return Response(WordSerializer(word_obj, context={"request": request}).data)


class SaveWordView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, word_id):
        try:
            word = Word.objects.get(id=word_id)
        except Word.DoesNotExist:
            return Response({"error": "Word not found"}, status=404)
        uw, created = UserWord.objects.get_or_create(user=request.user, word=word)
        return Response({"saved": True, "created": created})

    def delete(self, request, word_id):
        UserWord.objects.filter(user=request.user, word_id=word_id).delete()
        return Response({"saved": False})


class SavedWordsView(generics.ListAPIView):
    serializer_class = UserWordSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return UserWord.objects.filter(user=self.request.user).select_related("word")


class PracticeWordView(APIView):
    """Get random words by level for practice"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        level = request.query_params.get("level", "B1")
        words = list(Word.objects.filter(level=level).order_by("?")[:10])
        return Response(WordSerializer(words, many=True, context={"request": request}).data)


class BotVocabularyView(APIView):
    """Bot uchun: darajaga mos 20 ta so'z (BOT_SECRET bilan himoyalangan)"""
    permission_classes = []

    def get(self, request):
        from django.conf import settings
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        level = request.query_params.get("level", "B1")
        valid_levels = ['A1', 'A2', 'B1', 'B2', 'C1', 'C2']
        if level not in valid_levels:
            level = 'B1'

        words = list(Word.objects.filter(level=level).order_by("?")[:20])
        data = [
            {
                "word": w.word,
                "level": w.level,
                "definition": w.definition,
                "translation_uz": w.translation_uz,
                "examples": w.examples if isinstance(w.examples, list) else [],
            }
            for w in words
        ]
        return Response({"level": level, "words": data, "count": len(data)})
