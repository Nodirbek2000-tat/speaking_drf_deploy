import json
from datetime import datetime
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from django.db import models
from openai import OpenAI
from .models import PracticeCategory, PracticeScenario, PracticeSession, PracticeMessage
from .serializers import PracticeCategorySerializer, PracticeScenarioSerializer, PracticeSessionSerializer


client = OpenAI(api_key=settings.OPENAI_API_KEY)


class PracticeCategoryListView(generics.ListAPIView):
    serializer_class = PracticeCategorySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PracticeCategory.objects.filter(is_active=True).prefetch_related(
            models.Prefetch(
                'scenarios',
                queryset=PracticeScenario.objects.filter(is_active=True).order_by('difficulty', 'title')
            )
        ).order_by("order")


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


"""
=============================================================
webapp/views.py ga QO'SHING (mavjud practice viewlarga)
=============================================================
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json


@login_required
def scenario_detail(request, scenario_id):
    """Scenario detail JSON — practice.html openScenarioDetail() uchun"""
    from practice.models import PracticeScenario
    try:
        sc = PracticeScenario.objects.select_related('category').get(
            id=scenario_id, is_active=True
        )
    except PracticeScenario.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    return JsonResponse({
        'id': sc.id,
        'title': sc.title,
        'description': sc.description,
        'difficulty': sc.difficulty,
        'duration_minutes': sc.duration_minutes,
        'ai_role': sc.ai_role,
        'what_to_expect_list': sc.get_what_to_expect_list(),
        'category_id': sc.category_id,
        'category_name': sc.category.name,
        'category_icon': sc.category.icon,
    })


@login_required
@require_POST
def practice_start(request, scenario_id):
    """Practice sessionni boshlash"""
    from practice.models import PracticeScenario, PracticeSession
    from django.core.cache import cache

    # Free limit tekshirish
    user = request.user
    if not user.has_premium_active:
        from webapp.models import SiteSettings
        try:
            settings_obj = SiteSettings.objects.first()
            free_limit = settings_obj.free_practice_limit if settings_obj else 3
        except Exception:
            free_limit = 3

        if (user.practice_count or 0) >= free_limit:
            return JsonResponse({'error': 'free_limit'}, status=403)

    try:
        scenario = PracticeScenario.objects.get(id=scenario_id, is_active=True)
    except PracticeScenario.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    session = PracticeSession.objects.create(
        user=user,
        scenario=scenario,
    )

    # WebSocket token
    import uuid
    ws_token = str(uuid.uuid4())
    cache.set(f"ws_token_{ws_token}", user.id, timeout=300)

    return JsonResponse({
        'session_id': session.id,
        'ws_token': ws_token,
        'scenario': {
            'id': scenario.id,
            'title': scenario.title,
            'ai_role': scenario.ai_role,
        }
    })


@login_required
@require_POST
def end_practice_session(request, session_id):
    """Practice sessionni tugatish va Celery tahlilni ishga tushirish"""
    from practice.models import PracticeSession
    from practice.tasks import analyze_practice_session

    try:
        session = PracticeSession.objects.get(
            id=session_id,
            user=request.user,
            is_completed=False
        )
    except PracticeSession.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    data = json.loads(request.body or '{}')
    duration = data.get('duration_seconds', 0)

    session.ended_at = timezone.now()
    session.duration_seconds = duration
    session.is_completed = True
    session.save(update_fields=['ended_at', 'duration_seconds', 'is_completed'])

    # Celery orqali tahlil (async)
    analyze_practice_session.delay(session.id)

    return JsonResponse({'ok': True, 'session_id': session.id})


@login_required
def session_analysis(request, session_id):
    """Tahlil natijasini polling uchun"""
    from practice.models import PracticeSession

    try:
        session = PracticeSession.objects.get(id=session_id, user=request.user)
    except PracticeSession.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    return JsonResponse({
        'analysis_done': session.analysis_done,
        'overall_score': session.overall_score,
        'grammar_score': session.grammar_score,
        'vocab_score': session.vocab_score,
        'pronunciation_score': session.pronunciation_score,
        'fluency_score': session.fluency_score,
        'tense_stats': session.tense_stats or {},
        'ai_feedback': session.ai_feedback or {},
    })


# ─── webapp/urls.py ga QO'SHING ──────────────────────────────────────────────
"""
urlpatterns += [
    path('practice/scenario/<int:scenario_id>/detail/', views.scenario_detail, name='scenario_detail'),
    path('practice/start/<int:scenario_id>/', views.practice_start, name='practice_start'),
    path('practice/session/<int:session_id>/end/', views.end_practice_session, name='end_practice_session'),
    path('practice/session/<int:session_id>/analysis/', views.session_analysis, name='session_analysis'),
]
"""


# ─── practice/serializers.py ga QO'SHING ─────────────────────────────────────
"""
class PracticeScenarioSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_icon = serializers.CharField(source='category.icon', read_only=True)
    what_to_expect_list = serializers.SerializerMethodField()

    class Meta:
        model = PracticeScenario
        fields = [
            'id', 'category', 'category_name', 'category_icon',
            'title', 'description', 'ai_role', 'difficulty',
            'what_to_expect_list', 'duration_minutes', 'is_active',
        ]
        # ai_prompt ni CHIQARMAYMIZ — foydalanuvchi ko'rmasin

    def get_what_to_expect_list(self, obj):
        return obj.get_what_to_expect_list()
"""