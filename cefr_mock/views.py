import json
import random
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from openai import OpenAI
from .models import CEFRQuestion, CEFRSession, CEFRAnswer
from .serializers import CEFRSessionSerializer, CEFRQuestionSerializer

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class StartCEFRSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        p1 = list(CEFRQuestion.objects.filter(part=1, is_active=True))
        p2 = list(CEFRQuestion.objects.filter(part=2, is_active=True))
        p3 = list(CEFRQuestion.objects.filter(part=3, is_active=True))
        p4 = list(CEFRQuestion.objects.filter(part=4, is_active=True))

        if not p1:
            return Response({"error": "No CEFR questions. Admin must add questions."}, status=400)

        selected = (
            random.sample(p1, min(3, len(p1))) +
            (random.sample(p2, 1) if p2 else []) +
            (random.sample(p3, 1) if p3 else []) +
            (random.sample(p4, min(2, len(p4))) if p4 else [])
        )

        session = CEFRSession.objects.create(user=request.user)
        for q in selected:
            CEFRAnswer.objects.create(session=session, question=q)

        return Response({
            "session_id": session.id,
            "questions": CEFRQuestionSerializer(selected, many=True, context={"request": request}).data,
        })


class SubmitCEFRAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id, question_id):
        try:
            session = CEFRSession.objects.get(id=session_id, user=request.user, is_completed=False)
            answer = CEFRAnswer.objects.get(session=session, question_id=question_id)
        except (CEFRSession.DoesNotExist, CEFRAnswer.DoesNotExist):
            return Response({"error": "Not found"}, status=404)

        answer.transcript = request.data.get("transcript", "")
        answer.duration_seconds = request.data.get("duration_seconds", 0)
        answer.save()
        return Response({"status": "saved"})


class FinishCEFRSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = CEFRSession.objects.get(id=session_id, user=request.user, is_completed=False)
        except CEFRSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        answers = list(session.answers.select_related('question').all())
        qa_parts = []
        for ans in answers:
            part_num = ans.question.part
            q_text = ans.question.question
            a_text = ans.transcript if ans.transcript else '(no answer)'
            dur = ans.duration_seconds
            qa_parts.append('[Part ' + str(part_num) + '] Q: ' + q_text + '\nA: ' + a_text + '\nDuration: ' + str(dur) + 's')
        qa_text = '\n\n'.join(qa_parts)

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a CEFR language examiner. Score from 1-75. A1: 1-14, A2: 15-34, B1: 35-50, B2: 51-65, C1: 66-75. Evaluate: Range, Accuracy, Fluency, Interaction, Coherence."},
                {"role": "user", "content": f"""Evaluate this CEFR Speaking test:

{qa_text}

Return JSON:
{{
  "score": 58,
  "level": "B2",
  "range": 7.5,
  "accuracy": 7.0,
  "fluency": 8.0,
  "interaction": 7.5,
  "coherence": 7.0,
  "errors": [{{"error": "...", "correction": "...", "explanation": "..."}}],
  "strengths": ["..."],
  "improvements": ["..."],
  "summary": "Overall feedback"
}}"""}
            ],
            response_format={"type": "json_object"},
            max_tokens=1000
        )
        result = json.loads(resp.choices[0].message.content)
        session.score = result.get("score", 50)
        session.level = CEFRSession.score_to_level(session.score)
        session.feedback = result
        session.ended_at = timezone.now()
        session.is_completed = True
        session.save()

        request.user.cefr_count += 1
        request.user.save(update_fields=["cefr_count"])

        return Response(CEFRSessionSerializer(session).data)


class MyCEFRSessionsView(generics.ListAPIView):
    serializer_class = CEFRSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CEFRSession.objects.filter(user=self.request.user, is_completed=True)


class BotCEFRQuestionsView(APIView):
    """Bot uchun: random CEFR savollar (BOT_SECRET bilan himoyalangan)"""
    permission_classes = []

    def get(self, request):
        from django.conf import settings
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        p1 = list(CEFRQuestion.objects.filter(part=1, is_active=True))
        p2 = list(CEFRQuestion.objects.filter(part=2, is_active=True))
        p3 = list(CEFRQuestion.objects.filter(part=3, is_active=True))
        p4 = list(CEFRQuestion.objects.filter(part=4, is_active=True))

        if not p1:
            return Response({"questions": []})

        selected = (
            random.sample(p1, min(3, len(p1))) +
            (random.sample(p2, 1) if p2 else []) +
            (random.sample(p3, 1) if p3 else []) +
            (random.sample(p4, min(2, len(p4))) if p4 else [])
        )

        data = [
            {
                "id": q.id,
                "part": q.part,
                "question": q.question,
                "image_file_id": q.telegram_file_id or "",
                "instruction": q.instruction or "",
                "extra_info": "",
            }
            for q in selected
        ]
        return Response({"questions": data})
