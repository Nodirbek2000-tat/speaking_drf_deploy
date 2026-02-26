import json
import random
from rest_framework import generics
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from openai import OpenAI
from .models import IELTSQuestion, IELTSSession, IELTSAnswer
from .serializers import IELTSSessionSerializer, IELTSQuestionSerializer

client = OpenAI(api_key=settings.OPENAI_API_KEY)


class StartIELTSSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        part1_qs = list(IELTSQuestion.objects.filter(part=1, is_active=True))
        part2_qs = list(IELTSQuestion.objects.filter(part=2, is_active=True))
        part3_qs = list(IELTSQuestion.objects.filter(part=3, is_active=True))

        if not part1_qs or not part2_qs or not part3_qs:
            return Response({"error": "Not enough questions. Admin must add questions first."}, status=400)

        selected = (
            random.sample(part1_qs, min(3, len(part1_qs))) +
            random.sample(part2_qs, min(1, len(part2_qs))) +
            random.sample(part3_qs, min(3, len(part3_qs)))
        )

        session = IELTSSession.objects.create(user=request.user)
        for q in selected:
            IELTSAnswer.objects.create(session=session, question=q)

        return Response({
            "session_id": session.id,
            "questions": IELTSQuestionSerializer(selected, many=True).data,
        })


class SubmitIELTSAnswerView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id, question_id):
        try:
            session = IELTSSession.objects.get(id=session_id, user=request.user, is_completed=False)
            answer = IELTSAnswer.objects.get(session=session, question_id=question_id)
        except (IELTSSession.DoesNotExist, IELTSAnswer.DoesNotExist):
            return Response({"error": "Not found"}, status=404)

        transcript = request.data.get("transcript", "")
        answer.transcript = transcript
        answer.save()
        return Response({"status": "saved"})


class FinishIELTSSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = IELTSSession.objects.get(id=session_id, user=request.user, is_completed=False)
        except IELTSSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        answers = list(session.answers.select_related('question').all())
        qa_parts = []
        for ans in answers:
            part_num = ans.question.part
            q_text = ans.question.question
            a_text = ans.transcript if ans.transcript else '(no answer)'
            qa_parts.append('[Part ' + str(part_num) + '] Q: ' + q_text + '\nA: ' + a_text)
        qa_text = '\n\n'.join(qa_parts)

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a strict but fair IELTS Speaking examiner. Evaluate responses based on 4 criteria: Fluency & Coherence, Lexical Resource, Grammatical Range & Accuracy, Pronunciation. Give band scores from 1.0 to 9.0 in 0.5 increments."},
                {"role": "user", "content": f"""Evaluate this IELTS Speaking test:

{qa_text}

Return JSON:
{{
  "overall_band": 6.5,
  "sub_scores": {{"fluency": 7.0, "lexical": 6.5, "grammar": 6.5, "pronunciation": 6.0}},
  "strengths": ["strength 1", "strength 2"],
  "improvements": ["area 1", "area 2"],
  "mistakes": [
    {{"error": "...", "correction": "...", "explanation": "..."}}
  ],
  "recommendations": ["tip 1", "tip 2", "tip 3"]
}}"""}
            ],
            response_format={"type": "json_object"},
            max_tokens=1200
        )
        result = json.loads(resp.choices[0].message.content)
        session.overall_band = result.get("overall_band")
        session.sub_scores = result.get("sub_scores")
        session.strengths = result.get("strengths")
        session.improvements = result.get("improvements")
        session.mistakes = result.get("mistakes")
        session.recommendations = result.get("recommendations")
        session.ended_at = timezone.now()
        session.is_completed = True
        session.save()

        request.user.ielts_count += 1
        request.user.save(update_fields=["ielts_count"])

        return Response(IELTSSessionSerializer(session).data)


class MyIELTSSessionsView(generics.ListAPIView):
    serializer_class = IELTSSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return IELTSSession.objects.filter(user=self.request.user, is_completed=True)


class BotIELTSQuestionsView(APIView):
    """Bot uchun: random IELTS savollar — Part 3 Part 2 ga bog'liq (BOT_SECRET)"""
    permission_classes = []

    def get(self, request):
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        p1 = list(IELTSQuestion.objects.filter(part=1, is_active=True))
        p2 = list(IELTSQuestion.objects.filter(part=2, is_active=True))

        if not p1 or not p2:
            return Response({"questions": []})

        part1_selected = random.sample(p1, min(3, len(p1)))
        part2_q = random.choice(p2)

        part3_related = list(part2_q.part3_follow_up.filter(is_active=True))
        if not part3_related:
            part3_related = list(
                IELTSQuestion.objects.filter(
                    part=3, is_active=True, related_part2__isnull=True
                )
            )
        if not part3_related:
            part3_related = list(IELTSQuestion.objects.filter(part=3, is_active=True))

        if not part3_related:
            return Response({"questions": []})

        part3_selected = random.sample(part3_related, min(3, len(part3_related)))

        selected = part1_selected + [part2_q] + part3_selected
        data = [
            {
                "id": q.id,
                "part": q.part,
                "question": q.question,
                "cue_card_points": q.cue_card_points or [],
            }
            for q in selected
        ]
        return Response({"questions": data})
