import re
from collections import Counter
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.utils import timezone
from django.conf import settings
from .models import User, BotActivity, UserTenseStats
from .serializers import RegisterSerializer, LoginSerializer, UserSerializer, UserUpdateSerializer


class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        from rest_framework_simplejwt.tokens import RefreshToken
        tokens = RefreshToken.for_user(user)
        return Response({
            'access': str(tokens.access_token),
            'refresh': str(tokens),
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class ProfileView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method in ['PUT', 'PATCH']:
            return UserUpdateSerializer
        return UserSerializer

    def get_object(self):
        return self.request.user

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return super().update(request, *args, **kwargs)


class SetOnlineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.is_online = True
        request.user.last_seen = timezone.now()
        request.user.save(update_fields=['is_online', 'last_seen'])
        return Response({'status': 'online'})


class SetOfflineView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        request.user.is_online = False
        request.user.last_seen = timezone.now()
        request.user.save(update_fields=['is_online', 'last_seen'])
        return Response({'status': 'offline'})


class StatisticsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        from ielts_mock.models import IELTSSession
        from cefr_mock.models import CEFRSession

        ratings = user.received_ratings.all()
        avg_rating = round(sum(r.rating for r in ratings) / ratings.count(), 1) if ratings.exists() else None

        ielts_sessions = IELTSSession.objects.filter(user=user, is_completed=True).order_by('ended_at')
        cefr_sessions = CEFRSession.objects.filter(user=user, is_completed=True).order_by('ended_at')

        ielts_history = [
            {"band": s.overall_band, "date": s.ended_at.strftime('%d.%m') if s.ended_at else "—"}
            for s in ielts_sessions
        ]
        cefr_history = [
            {"score": s.score, "level": s.level, "date": s.ended_at.strftime('%d.%m') if s.ended_at else "—"}
            for s in cefr_sessions
        ]

        ielts_improvement = None
        if len(ielts_history) >= 2:
            first = ielts_history[0].get('band')
            last = ielts_history[-1].get('band')
            if first and last:
                ielts_improvement = round(last - first, 1)

        cefr_improvement = None
        if len(cefr_history) >= 2:
            first = cefr_history[0].get('score')
            last = cefr_history[-1].get('score')
            if first and last:
                cefr_improvement = last - first

        last_ielts = ielts_sessions.last()
        last_cefr = cefr_sessions.last()

        return Response({
            'chat_count': user.chat_count,
            'practice_count': user.practice_count,
            'ielts_count': user.ielts_count,
            'cefr_count': user.cefr_count,
            'avg_rating': avg_rating,
            'last_ielts_band': last_ielts.overall_band if last_ielts else None,
            'last_cefr_score': last_cefr.score if last_cefr else None,
            'last_cefr_level': last_cefr.level if last_cefr else None,
            'ielts_history': ielts_history,
            'cefr_history': cefr_history,
            'ielts_improvement': ielts_improvement,
            'cefr_improvement': cefr_improvement,
            'referral_code': user.referral_code,
            'referrals_count': user.given_referrals.count(),
            'is_premium': user.has_premium_active,
            'premium_expires': user.premium_expires,
            'can_search': user.can_search_partner,
            'free_searches_used': user.free_searches_used,
        })


class BotActivityLogView(APIView):
    """Bot foydalanuvchi faoliyatlarini log qilish"""
    permission_classes = []

    def post(self, request):
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        telegram_id = request.data.get("telegram_id")
        if not telegram_id:
            return Response({"error": "telegram_id required"}, status=400)

        full_name = request.data.get("full_name", "")
        username = request.data.get("username", "")
        activity_type = request.data.get("activity_type", "")

        BotActivity.objects.create(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
            activity_type=activity_type,
            data=request.data.get("data", {}),
        )

        # /start bosganida DRF User modelida ham yarat yoki yangilang
        if activity_type == "start":
            name_parts = full_name.split(None, 1)
            first_name = name_parts[0] if name_parts else full_name
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            try:
                user = User.objects.get(telegram_id=telegram_id)
                update_fields = []
                if first_name and user.first_name != first_name:
                    user.first_name = first_name
                    update_fields.append("first_name")
                if last_name is not None and user.last_name != last_name:
                    user.last_name = last_name
                    update_fields.append("last_name")
                if username:
                    tg_un = username.lower()
                    if user.username != tg_un and not User.objects.filter(username=tg_un).exclude(pk=user.pk).exists():
                        user.username = tg_un
                        update_fields.append("username")
                if update_fields:
                    user.save(update_fields=update_fields)
            except User.DoesNotExist:
                base_un = username.lower() if username else f"tg_{telegram_id}"
                final_un = base_un
                counter = 1
                while User.objects.filter(username=final_un).exists():
                    final_un = f"{base_un}_{counter}"
                    counter += 1
                User.objects.create_user(
                    username=final_un,
                    first_name=first_name,
                    last_name=last_name,
                    telegram_id=telegram_id,
                    password=None,
                )

        return Response({"status": "logged"})


class BotStatisticsView(APIView):
    """Bot uchun to'liq statistika va tahlil (DRF dan)"""
    permission_classes = []

    def get(self, request):
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        telegram_id = request.query_params.get("telegram_id")
        if not telegram_id:
            return Response({"error": "telegram_id required"}, status=400)

        today = timezone.now().date()

        ielts_acts = list(BotActivity.objects.filter(
            telegram_id=telegram_id, activity_type="ielts_mock"
        ).order_by("created_at"))

        cefr_acts = list(BotActivity.objects.filter(
            telegram_id=telegram_id, activity_type="cefr_mock"
        ).order_by("created_at"))

        ai_acts = BotActivity.objects.filter(
            telegram_id=telegram_id, activity_type="ai_chat"
        ).count()

        # ─── IELTS tarixi ───────────────────────────────────
        ielts_history = []
        for a in ielts_acts:
            band = a.data.get("band") or a.data.get("overall_band")
            if band:
                ielts_history.append({
                    "band": float(band),
                    "date": a.created_at.strftime('%d.%m'),
                    "sub_scores": a.data.get("sub_scores", {}),
                })

        # ─── CEFR tarixi ────────────────────────────────────
        cefr_history = []
        for a in cefr_acts:
            score = a.data.get("score")
            if score:
                cefr_history.append({
                    "score": int(score),
                    "level": a.data.get("level", "—"),
                    "date": a.created_at.strftime('%d.%m'),
                })

        # ─── IELTS o'sish ───────────────────────────────────
        ielts_improvement = None
        if len(ielts_history) >= 2:
            ielts_improvement = round(ielts_history[-1]['band'] - ielts_history[0]['band'], 1)

        # ─── CEFR o'sish ────────────────────────────────────
        cefr_improvement = None
        if len(cefr_history) >= 2:
            cefr_improvement = cefr_history[-1]['score'] - cefr_history[0]['score']

        # ─── IELTS zaif qismlar (sub-scores o'rtacha) ───────
        weak_areas = []
        if ielts_history:
            totals = {'fluency': [], 'lexical': [], 'grammar': [], 'pronunciation': []}
            for h in ielts_history:
                for k in totals:
                    v = h['sub_scores'].get(k)
                    if v:
                        totals[k].append(float(v))
            avgs = {k: round(sum(v) / len(v), 1) for k, v in totals.items() if v}
            if avgs:
                sorted_areas = sorted(avgs.items(), key=lambda x: x[1])
                labels = {
                    'fluency': 'Fluency & Coherence',
                    'lexical': 'Lexical Resource',
                    'grammar': 'Grammatical Range',
                    'pronunciation': 'Pronunciation',
                }
                for name, score in sorted_areas[:2]:
                    weak_areas.append({'skill': labels.get(name, name), 'avg': score})

        # ─── Bugun qilingan mocklar ──────────────────────────
        today_ielts = sum(1 for a in ielts_acts if a.created_at.date() == today)
        today_cefr = sum(1 for a in cefr_acts if a.created_at.date() == today)

        # ─── So'z chastotasi tahlili ─────────────────────────
        STOP = {
            'that','this','with','from','they','have','been','were','will','would',
            'could','should','which','their','about','there','when','also','more',
            'some','what','like','very','just','than','then','your','most','into',
            'over','only','even','back','such','each','much','make','take','know',
            'think','come','good','well','many','time','year','work','people',
            'because','really','things','dont','cant','said','want','need','going',
        }
        all_words = []
        for act in ielts_acts + cefr_acts:
            for t in act.data.get("transcripts", []):
                if t:
                    words = re.findall(r'\b[a-zA-Z]{4,}\b', t.lower())
                    all_words.extend(w for w in words if w not in STOP)

        top_words = [{"word": w, "count": c} for w, c in Counter(all_words).most_common(10)]

        return Response({
            "total_mocks": len(ielts_acts) + len(cefr_acts),
            "total_ielts": len(ielts_acts),
            "total_cefr": len(cefr_acts),
            "total_ai_chats": ai_acts,
            "today_ielts": today_ielts,
            "today_cefr": today_cefr,
            "ielts_history": ielts_history,
            "cefr_history": cefr_history,
            "ielts_improvement": ielts_improvement,
            "cefr_improvement": cefr_improvement,
            "weak_areas": weak_areas,
            "top_words": top_words,
            # So'nggi natijalar
            "last_ielts_band": ielts_history[-1]['band'] if ielts_history else None,
            "last_cefr_score": cefr_history[-1]['score'] if cefr_history else None,
            "last_cefr_level": cefr_history[-1]['level'] if cefr_history else None,
        })


class TenseSyncView(APIView):
    """Bot dan kunlik tense statistikasini saqlash"""
    permission_classes = []

    def post(self, request):
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        telegram_id = request.data.get("telegram_id")
        if not telegram_id:
            return Response({"error": "telegram_id required"}, status=400)

        tense_data = request.data.get("tense_data", {})
        if not tense_data:
            return Response({"status": "no data"})

        today = timezone.now().date()
        for tense_name, counts in tense_data.items():
            usage = counts.get("usage", 0)
            correct = counts.get("correct", 0)
            if usage <= 0:
                continue
            obj, created = UserTenseStats.objects.get_or_create(
                telegram_id=telegram_id,
                date=today,
                tense_name=tense_name,
                defaults={"usage_count": usage, "correct_count": correct},
            )
            if not created:
                obj.usage_count += usage
                obj.correct_count += correct
            obj.accuracy = round(obj.correct_count / obj.usage_count * 100, 1) if obj.usage_count > 0 else 0
            obj.save()

        return Response({"status": "synced"})

    def get(self, request):
        """Tense statistikasini olish (30 kunlik)"""
        secret = request.headers.get("X-Bot-Secret", "")
        if secret != settings.BOT_SECRET:
            return Response({"error": "Forbidden"}, status=403)

        telegram_id = request.query_params.get("telegram_id")
        days = int(request.query_params.get("days", 30))
        if not telegram_id:
            return Response({"error": "telegram_id required"}, status=400)

        from datetime import timedelta
        start = timezone.now().date() - timedelta(days=days)
        stats = UserTenseStats.objects.filter(telegram_id=telegram_id, date__gte=start)

        summary = {}
        for s in stats:
            if s.tense_name not in summary:
                summary[s.tense_name] = {"usage": 0, "correct": 0}
            summary[s.tense_name]["usage"] += s.usage_count
            summary[s.tense_name]["correct"] += s.correct_count

        for tense in summary:
            u = summary[tense]["usage"]
            summary[tense]["accuracy"] = round(summary[tense]["correct"] / u * 100) if u > 0 else 0

        return Response({"tense_stats": summary})


class UserTenseStatsView(APIView):
    """JWT auth bilan foydalanuvchi tense statistikasini olish (today va monthly)"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import timedelta
        user = request.user
        telegram_id = str(user.telegram_id) if user.telegram_id else None
        if not telegram_id:
            return Response({"today": {}, "monthly": {}})

        today = timezone.now().date()
        month_start = today - timedelta(days=30)

        today_stats = UserTenseStats.objects.filter(telegram_id=telegram_id, date=today)
        monthly_stats = UserTenseStats.objects.filter(telegram_id=telegram_id, date__gte=month_start)

        def aggregate(qs):
            result = {}
            for s in qs:
                if s.tense_name not in result:
                    result[s.tense_name] = {"usage": 0, "correct": 0}
                result[s.tense_name]["usage"] += s.usage_count
                result[s.tense_name]["correct"] += s.correct_count
            for tense in result:
                u = result[tense]["usage"]
                result[tense]["accuracy"] = round(result[tense]["correct"] / u * 100) if u > 0 else 0
            return result

        return Response({
            "today": aggregate(today_stats),
            "monthly": aggregate(monthly_stats),
        })


class MyAnalysisView(APIView):
    """JWT auth bilan foydalanuvchi AI tahlili"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from datetime import timedelta
        import os
        from openai import OpenAI

        user = request.user
        telegram_id = str(user.telegram_id) if user.telegram_id else None
        if not telegram_id:
            return Response({"analysis": "", "weak_tenses": [], "recommendations": []})

        today = timezone.now().date()
        month_start = today - timedelta(days=30)

        monthly_stats = UserTenseStats.objects.filter(telegram_id=telegram_id, date__gte=month_start)
        today_stats = UserTenseStats.objects.filter(telegram_id=telegram_id, date=today)

        # Aggregate stats
        def aggregate(qs):
            result = {}
            for s in qs:
                if s.tense_name not in result:
                    result[s.tense_name] = {"usage": 0, "correct": 0}
                result[s.tense_name]["usage"] += s.usage_count
                result[s.tense_name]["correct"] += s.correct_count
            for tense in result:
                u = result[tense]["usage"]
                result[tense]["accuracy"] = round(result[tense]["correct"] / u * 100) if u > 0 else 0
            return result

        monthly = aggregate(monthly_stats)
        today_data = aggregate(today_stats)

        # Zaif zamonlar (accuracy < 65%)
        weak_tenses = [
            {"tense": t, "accuracy": v["accuracy"], "usage": v["usage"]}
            for t, v in monthly.items()
            if v.get("accuracy", 100) < 65 and v.get("usage", 0) >= 2
        ]
        weak_tenses.sort(key=lambda x: x["accuracy"])

        # Bugungi o'sish (today vs monthly avg)
        growth_today = None
        if today_data and monthly:
            best_growth = None
            best_pct = 0
            for tense, tv in today_data.items():
                mv = monthly.get(tense, {})
                if mv and mv.get("accuracy", 0) > 0:
                    diff = tv["accuracy"] - mv["accuracy"]
                    if diff > best_pct:
                        best_pct = diff
                        best_growth = {"tense": tense, "percent": diff}
            growth_today = best_growth

        # AI tahlil
        analysis_text = ""
        recommendations = []
        openai_key = os.environ.get("OPENAI_API_KEY", "")
        if openai_key and monthly:
            try:
                tense_lines = []
                for t, v in monthly.items():
                    tense_lines.append(f"- {t}: {v['accuracy']}% accuracy ({v['usage']} uses)")
                prompt = (
                    "Analyze this English grammar tense statistics for a language learner:\n\n"
                    + "\n".join(tense_lines)
                    + "\n\nProvide in English:\n"
                    "1. Brief overall assessment (1-2 sentences)\n"
                    "2. Biggest weaknesses and why\n"
                    "3. Three specific, actionable recommendations\n"
                    "Keep it concise and encouraging."
                )
                oai = OpenAI(api_key=openai_key)
                resp = oai.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are an English grammar coach analyzing student data."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=400
                )
                analysis_text = resp.choices[0].message.content.strip()
                # Parse recommendations (last 3 lines or bullet points)
                lines = [l.strip() for l in analysis_text.split("\n") if l.strip()]
                recommendations = [l for l in lines if l.startswith(("•", "-", "1.", "2.", "3.","*"))][-3:]
            except Exception:
                pass

        return Response({
            "analysis": analysis_text,
            "weak_tenses": weak_tenses[:3],
            "growth_today": growth_today,
            "recommendations": recommendations,
        })
