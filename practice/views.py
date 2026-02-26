import json
from datetime import datetime
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from openai import OpenAI
from .models import PracticeCategory, PracticeScenario, PracticeSession, PracticeMessage
from .serializers import PracticeCategorySerializer, PracticeScenarioSerializer, PracticeSessionSerializer


client = OpenAI(api_key=settings.OPENAI_API_KEY)


class PracticeCategoryListView(generics.ListAPIView):
    serializer_class = PracticeCategorySerializer
    permission_classes = [IsAuthenticated]
    queryset = PracticeCategory.objects.prefetch_related("scenarios").all()


class PracticeScenarioListView(generics.ListAPIView):
    serializer_class = PracticeScenarioSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = PracticeScenario.objects.filter(is_active=True)
        category = self.request.query_params.get("category")
        difficulty = self.request.query_params.get("difficulty")
        if category:
            qs = qs.filter(category_id=category)
        if difficulty:
            qs = qs.filter(difficulty=difficulty)
        return qs


class StartPracticeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, scenario_id):
        try:
            scenario = PracticeScenario.objects.get(id=scenario_id, is_active=True)
        except PracticeScenario.DoesNotExist:
            return Response({"error": "Scenario not found"}, status=404)

        session = PracticeSession.objects.create(user=request.user, scenario=scenario)
        PracticeMessage.objects.create(
            session=session, role="assistant",
            content=f"Welcome! Let's practice: {scenario.title}. I'll be your AI conversation partner. {scenario.what_to_expect} Ready? Let's begin!"
        )
        return Response(PracticeSessionSerializer(session).data)


class SendPracticeMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = PracticeSession.objects.get(id=session_id, user=request.user, is_completed=False)
        except PracticeSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        content = request.data.get("content", "")
        if not content:
            return Response({"error": "Content required"}, status=400)

        PracticeMessage.objects.create(session=session, role="user", content=content)

        messages = list(session.messages.all())
        history = [
            {"role": "system", "content": session.scenario.ai_prompt}
        ] + [
            {"role": m.role if m.role == "user" else "assistant", "content": m.content}
            for m in messages
        ]

        resp = client.chat.completions.create(
            model="gpt-4o-mini", messages=history, max_tokens=300
        )
        ai_reply = resp.choices[0].message.content
        msg = PracticeMessage.objects.create(session=session, role="assistant", content=ai_reply)
        return Response({"role": "assistant", "content": ai_reply, "created_at": msg.created_at})


class EndPracticeSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        try:
            session = PracticeSession.objects.get(id=session_id, user=request.user, is_completed=False)
        except PracticeSession.DoesNotExist:
            return Response({"error": "Session not found"}, status=404)

        session.ended_at = timezone.now()
        session.duration_seconds = int((session.ended_at - session.started_at).total_seconds())
        session.is_completed = True
        session.save()

        messages = list(session.messages.filter(role="user"))
        if not messages:
            return Response(PracticeSessionSerializer(session).data)

        conversation = "\n".join([f"User: {m.content}" for m in messages])

        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert English language evaluator."},
                {"role": "user", "content": f"""Evaluate this English practice session ({session.scenario.title}):

{conversation}

Duration: {session.duration_seconds} seconds

Return JSON:
{{
  "overall_score": 7.5,
  "fluency": 7.0,
  "vocabulary": 8.0,
  "grammar": 7.5,
  "errors": [
    {{"error": "...", "correction": "...", "explanation": "..."}}
  ],
  "strengths": ["..."],
  "improvements": ["..."],
  "summary": "2-3 sentence overall feedback"
}}"""}
            ],
            response_format={"type": "json_object"},
            max_tokens=800
        )
        feedback = json.loads(resp.choices[0].message.content)
        session.ai_feedback = feedback
        session.overall_score = feedback.get("overall_score")
        session.save()

        request.user.practice_count += 1
        request.user.save(update_fields=["practice_count"])

        return Response(PracticeSessionSerializer(session).data)


class MyPracticeSessionsView(generics.ListAPIView):
    serializer_class = PracticeSessionSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PracticeSession.objects.filter(user=self.request.user, is_completed=True)
