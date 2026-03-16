import json
import random
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from openai import OpenAI
from .models import CEFRMock, CEFRQuestion, CEFRSession, CEFRAnswer
from .serializers import CEFRSessionSerializer, CEFRQuestionSerializer

client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ─── Bot: random CEFR mock ─────────────────────────────────────────────────────

class BotCEFRMockView(APIView):
    """Bot uchun: random bitta to'liq CEFR mock (BOT_SECRET bilan himoyalangan)"""
    permission_classes = []

    def get(self, request):
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        mocks = list(CEFRMock.objects.filter(is_active=True))
        if not mocks:
            return Response({"error": "No active mocks"}, status=404)

        mock = random.choice(mocks)

        def img_url(field):
            if field:
                return request.build_absolute_uri(field.url)
            return ""

        return Response({
            "id": mock.id,
            # Part 1.1
            "p1_q1": mock.p1_q1,
            "p1_q2": mock.p1_q2,
            "p1_q3": mock.p1_q3,
            # Part 1.2
            "p1_2_instruction": mock.p1_2_instruction,
            "p1_2_q1":      mock.p1_2_q1,
            "p1_2_q1_img1": img_url(mock.p1_2_q1_img1),
            "p1_2_q1_img2": img_url(mock.p1_2_q1_img2),
            "p1_2_q2":      mock.p1_2_q2,
            "p1_2_q2_img1": img_url(mock.p1_2_q2_img1),
            "p1_2_q2_img2": img_url(mock.p1_2_q2_img2),
            "p1_2_q3":      mock.p1_2_q3,
            "p1_2_q3_img1": img_url(mock.p1_2_q3_img1),
            "p1_2_q3_img2": img_url(mock.p1_2_q3_img2),
            # Part 2
            "p2_question":    mock.p2_question,
            "p2_instruction": mock.p2_instruction,
            "p2_image_url":   img_url(mock.p2_image),
            # Part 3
            "p3_topic":       mock.p3_topic,
            "p3_for_q1":      mock.p3_for_q1,
            "p3_for_q2":      mock.p3_for_q2,
            "p3_for_q3":      mock.p3_for_q3,
            "p3_against_q1":  mock.p3_against_q1,
            "p3_against_q2":  mock.p3_against_q2,
            "p3_against_q3":  mock.p3_against_q3,
        })


# ─── Session views (web app uchun) ────────────────────────────────────────────

class StartCEFRSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        p1 = list(CEFRQuestion.objects.filter(part=1, is_active=True))
        p2 = list(CEFRQuestion.objects.filter(part=2, is_active=True))
        p3 = list(CEFRQuestion.objects.filter(part=3, is_active=True))

        if not p1:
            return Response({"error": "No CEFR questions."}, status=400)

        selected = (
            random.sample(p1, min(3, len(p1))) +
            (random.sample(p2, 1) if p2 else []) +
            (random.sample(p3, 1) if p3 else [])
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
            answer  = CEFRAnswer.objects.get(session=session, question_id=question_id)
        except (CEFRSession.DoesNotExist, CEFRAnswer.DoesNotExist):
            return Response({"error": "Not found"}, status=404)

        answer.transcript        = request.data.get("transcript", "")
        answer.duration_seconds  = request.data.get("duration_seconds", 0)
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
            qa_parts.append(
                '[Part ' + str(ans.question.part) + '] Q: ' + ans.question.question +
                '\nA: ' + (ans.transcript or '(no answer)') +
                '\nDuration: ' + str(ans.duration_seconds) + 's'
            )
        qa_text = '\n\n'.join(qa_parts)

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a CEFR language examiner. Score from 1-75."},
                {"role": "user", "content": f"Evaluate this CEFR Speaking test:\n\n{qa_text}\n\nReturn JSON: {{\"score\":58,\"level\":\"B2\",\"summary\":\"...\",\"strengths\":[],\"improvements\":[],\"errors\":[]}}"},
            ],
            response_format={"type": "json_object"},
            max_tokens=1000
        )
        result = json.loads(resp.choices[0].message.content)
        session.score      = result.get("score", 50)
        session.level      = CEFRSession.score_to_level(session.score)
        session.feedback   = result
        session.ended_at   = timezone.now()
        session.is_completed = True
        session.save()

        request.user.cefr_count += 1
        request.user.save(update_fields=["cefr_count"])

        return Response(CEFRSessionSerializer(session).data)


class MyCEFRSessionsView(generics.ListAPIView):
    serializer_class   = CEFRSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CEFRSession.objects.filter(user=self.request.user, is_completed=True)
