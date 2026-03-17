import json
import logging
from datetime import timedelta, date
from functools import wraps

logger = logging.getLogger(__name__)

from django.conf import settings
from django.contrib.auth import login, logout
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, IntegerField
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.views.decorators.http import require_POST

from .auth import verify_telegram_webapp, get_or_create_webapp_user
from .models import AppSettings, PaymentCard, RequiredChannel, VoiceRoom, VoiceRating


# ─── Auth Decorator ───────────────────────────────────────────────────────────

def webapp_login_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/webapp/')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─── Auth Views ───────────────────────────────────────────────────────────────

def index(request):
    """Entry point — shows login/loading page for Telegram WebApp auth"""
    # Faqat Telegram orqali autentifikatsiya qilingan userlarni o'tkazish.
    # Superuser yoki admin session bo'lsa — qayta Telegram auth qilinsin.
    user = request.user
    if user.is_authenticated and getattr(user, 'telegram_id', None):
        return redirect('/webapp/home/')
    # Eski session ni tozalash (masalan admin session qolgan bo'lsa)
    if user.is_authenticated and not getattr(user, 'telegram_id', None):
        logout(request)
    return render(request, 'webapp/index.html', {'debug': settings.DEBUG})


@csrf_exempt
def auth_view(request):
    """Verify Telegram WebApp initData and login user"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    try:
        body = json.loads(request.body)
        init_data = body.get('initData', '')
    except Exception:
        init_data = request.POST.get('initData', '')

    bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')

    # Debug rejimda test login (faqat dev uchun, superuser EMAS — real Telegram user)
    if settings.DEBUG and init_data == 'test':
        from users.models import User
        test_tg_id = 999999999
        user, created = User.objects.get_or_create(
            telegram_id=test_tg_id,
            defaults={'username': 'test_webapp_user', 'first_name': 'Test', 'last_name': 'User'}
        )
        logout(request)
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        return JsonResponse({'ok': True, 'redirect': '/webapp/home/', 'created': created})

    # Real Telegram WebApp auth
    user_data = verify_telegram_webapp(init_data, bot_token)
    if not user_data:
        logger.warning(
            f"[WebApp Auth] FAILED — token_ok={bool(bot_token)}, "
            f"initData_len={len(init_data)}, preview={init_data[:80]!r}"
        )
        if settings.DEBUG:
            return JsonResponse({
                'ok': False,
                'error': 'Invalid initData',
                'debug': {
                    'token_present': bool(bot_token),
                    'initData_len': len(init_data),
                    'initData_preview': init_data[:100],
                }
            }, status=401)
        return JsonResponse({'ok': False, 'error': 'Invalid initData'}, status=401)

    user, created = get_or_create_webapp_user(user_data)
    if not user:
        return JsonResponse({'ok': False, 'error': 'Failed to create user'}, status=500)

    logger.info(f"[WebApp Auth] OK — user={user.id} ({user.username}), telegram_id={user.telegram_id}, created={created}")

    # Eski sessionni tozalab yangi user bilan login qilish
    logout(request)
    user.backend = 'django.contrib.auth.backends.ModelBackend'
    login(request, user)

    # Yangi user yoki ism yo'q bo'lsa → setup sahifasiga
    needs_setup = created or not user.first_name
    redirect_url = '/webapp/setup/' if needs_setup else '/webapp/home/'
    return JsonResponse({'ok': True, 'redirect': redirect_url, 'created': created})


def logout_view(request):
    logout(request)
    return redirect('/webapp/')


# ─── Setup (first-time onboarding) ───────────────────────────────────────────

@webapp_login_required
def setup(request):
    """First-time setup: name + gender"""
    user = request.user
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        gender = request.POST.get('gender', '').strip()
        update_fields = []
        if first_name:
            user.first_name = first_name
            update_fields.append('first_name')
        if last_name is not None:
            user.last_name = last_name
            update_fields.append('last_name')
        if gender in ('male', 'female', 'other'):
            user.gender = gender
            update_fields.append('gender')
        if update_fields:
            user.save(update_fields=update_fields)
        return redirect('/webapp/home/')
    # Already set up → go home
    if user.first_name and user.gender:
        return redirect('/webapp/home/')
    return render(request, 'webapp/setup.html', {'user': user})


# ─── Home ─────────────────────────────────────────────────────────────────────

@ensure_csrf_cookie
@webapp_login_required
def home(request):
    user = request.user
    today = timezone.localdate()

    # Week days (Mon to Sun of current week)
    monday = today - timedelta(days=today.weekday())
    week_days = []
    for i in range(7):
        day = monday + timedelta(days=i)
        has_activity = VoiceRoom.objects.filter(
            Q(user1=user) | Q(user2=user),
            started_at__date=day,
            status='ended'
        ).exists()
        week_days.append({
            'date': day,
            'label': ['Du', 'Se', 'Ch', 'Pa', 'Ju', 'Sh', 'Ya'][i],
            'is_today': day == today,
            'has_activity': has_activity,
        })

    # Streak calculation
    streak = 0
    check_day = today
    while True:
        has = VoiceRoom.objects.filter(
            Q(user1=user) | Q(user2=user),
            started_at__date=check_day,
            status='ended'
        ).exists()
        if not has:
            break
        streak += 1
        check_day -= timedelta(days=1)

    # Stats
    total_messages = 0  # voice messages count
    voice_rooms = VoiceRoom.objects.filter(
        Q(user1=user) | Q(user2=user)
    ).count()

    # Recent conversations (for home page)
    recent_convos = VoiceRoom.objects.filter(
        Q(user1=user) | Q(user2=user),
        status='ended'
    ).select_related('user1', 'user2').order_by('-ended_at')[:10]

    convos_data = []
    for room in recent_convos:
        partner = room.get_partner(user)
        if room.partner_type == 'ai':
            partner_name = 'AI (Alex)'
            partner_username = 'ai'
        elif partner:
            partner_name = partner.get_full_name() or partner.username
            partner_username = partner.username
        else:
            partner_name = 'Unknown'
            partner_username = ''
        m, s = divmod(room.duration_seconds, 60)
        convos_data.append({
            'partner_name': partner_name,
            'partner_username': partner_username,
            'duration': f"{m}:{s:02d}" if room.duration_seconds else '0:00',
            'date': room.ended_at,
            'room_id': room.id,
        })

    # Partner feedback (last 10 ratings for this user)
    feedbacks = VoiceRating.objects.filter(
        rated_user=user
    ).select_related('rater').order_by('-created_at')[:10]

    # Progress (premium only)
    progress_data = None
    if user.has_premium_active:
        from ielts_mock.models import IELTSSession
        from cefr_mock.models import CEFRSession
        from practice.models import PracticeSession

        ielts_sessions = IELTSSession.objects.filter(
            user=user, is_completed=True
        ).order_by('-started_at')[:5]
        cefr_sessions = CEFRSession.objects.filter(
            user=user, is_completed=True
        ).order_by('-started_at')[:5]
        practice_sessions = PracticeSession.objects.filter(
            user=user, is_completed=True
        ).order_by('-started_at')[:5]

        latest_ielts = ielts_sessions.first()
        latest_cefr = cefr_sessions.first()

        progress_data = {
            'ielts_sessions': ielts_sessions,
            'cefr_sessions': cefr_sessions,
            'practice_sessions': practice_sessions,
            'latest_ielts_band': latest_ielts.overall_band if latest_ielts else None,
            'latest_cefr_score': latest_cefr.score if latest_cefr else None,
            'latest_cefr_level': latest_cefr.level if latest_cefr else None,
            'practice_count': practice_sessions.count(),
        }

    return render(request, 'webapp/home.html', {
        'user': user,
        'week_days': week_days,
        'streak': streak,
        'voice_rooms_count': voice_rooms,
        'recent_convos': convos_data,
        'feedbacks': feedbacks,
        'progress_data': progress_data,
        'today': today,
    })


# ─── Speaking ─────────────────────────────────────────────────────────────────

@ensure_csrf_cookie
@webapp_login_required
def speaking(request):
    user = request.user
    settings_obj = AppSettings.get()

    # Free calls remaining
    free_calls_used = VoiceRoom.objects.filter(
        user1=user, partner_type='human', status='ended'
    ).count()
    free_calls_left = max(0, settings_obj.free_calls_limit - free_calls_used)
    can_call = user.has_premium_active or free_calls_left > 0

    # Recent conversations
    recent_rooms = VoiceRoom.objects.filter(
        Q(user1=user) | Q(user2=user)
    ).select_related('user1', 'user2').order_by('-started_at')[:20]

    convos = []
    for room in recent_rooms:
        partner = room.get_partner(user)
        if room.partner_type == 'ai':
            p_name = 'AI (Alex)'
            p_username = ''
        elif partner:
            p_name = partner.get_full_name() or partner.username
            p_username = partner.username
        else:
            p_name = 'Unknown'
            p_username = ''
        m, s = divmod(room.duration_seconds, 60)
        convos.append({
            'room_id': room.id,
            'partner_name': p_name,
            'partner_username': p_username,
            'partner_type': room.partner_type,
            'duration': f"{m}:{s:02d}",
            'date': room.started_at,
            'status': room.status,
            'has_rated': VoiceRating.objects.filter(room=room, rater=user).exists(),
        })

    return render(request, 'webapp/speaking-1.html', {
        'user': user,
        'can_call': can_call,
        'free_calls_left': free_calls_left,
        'is_premium': user.has_premium_active,
        'convos': convos,
        'settings': settings_obj,
    })


@csrf_exempt
@webapp_login_required
@require_POST
def rate_call(request, room_id):
    room = get_object_or_404(VoiceRoom, id=room_id)
    user = request.user

    # Verify user was in this room
    if room.user1 != user and room.user2 != user:
        return JsonResponse({'error': 'Bu xonada sizning ruxsatingiz yo\'q'}, status=403)

    if VoiceRating.objects.filter(room=room, rater=user).exists():
        return JsonResponse({'error': 'Siz allaqachon baho berdingiz'}, status=400)

    try:
        data = json.loads(request.body)
        rating = int(data.get('rating', 0))
        comment = data.get('comment', '')
    except Exception:
        return JsonResponse({'error': 'Invalid data'}, status=400)

    if not 1 <= rating <= 5:
        return JsonResponse({'error': 'Baho 1-5 orasida bo\'lishi kerak'}, status=400)

    rated_user = room.get_partner(user)
    VoiceRating.objects.create(
        room=room,
        rater=user,
        rated_user=rated_user,
        rating=rating,
        comment=comment,
    )
    return JsonResponse({'ok': True})


def speaking_history(request):
    """API: Return speaking history as JSON (for AJAX refresh)"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    user = request.user
    rooms = VoiceRoom.objects.filter(
        Q(user1=user) | Q(user2=user),
        status='ended'
    ).select_related('user1', 'user2').order_by('-ended_at')[:20]

    result = []
    for room in rooms:
        partner = room.get_partner(user)
        m, s = divmod(room.duration_seconds, 60)
        result.append({
            'id': room.id,
            'partner': partner.get_full_name() or partner.username if partner else 'AI',
            'duration': f"{m}:{s:02d}",
            'date': room.ended_at.isoformat() if room.ended_at else None,
        })
    return JsonResponse({'rooms': result})


# ─── Practice ─────────────────────────────────────────────────────────────────

@ensure_csrf_cookie
@webapp_login_required
def practice(request):
    from practice.models import PracticeCategory, PracticeScenario, PracticeSession

    categories = PracticeCategory.objects.prefetch_related('scenarios').all()
    recent_sessions = PracticeSession.objects.filter(
        user=request.user, is_completed=True
    ).select_related('scenario').order_by('-started_at')[:10]

    return render(request, 'webapp/practice.html', {
        'user': request.user,
        'categories': categories,
        'recent_sessions': recent_sessions,
    })


@webapp_login_required
def scenario_detail(request, scenario_id):
    """AJAX: Return scenario details as JSON"""
    from practice.models import PracticeScenario
    scenario = get_object_or_404(PracticeScenario, id=scenario_id, is_active=True)
    return JsonResponse({
        'id': scenario.id,
        'title': scenario.title,
        'description': scenario.description,
        'difficulty': scenario.difficulty,
        'what_to_expect': scenario.what_to_expect,
        'duration_minutes': scenario.duration_minutes,
        'category': scenario.category.name,
        'ai_role': scenario.ai_prompt[:100] + '...' if len(scenario.ai_prompt) > 100 else scenario.ai_prompt,
    })


@csrf_exempt
@webapp_login_required
def practice_start(request, scenario_id):
    """Create a new practice session and redirect to it"""
    from practice.models import PracticeScenario, PracticeSession
    scenario = get_object_or_404(PracticeScenario, id=scenario_id, is_active=True)

    if request.method == 'POST':
        session = PracticeSession.objects.create(
            user=request.user,
            scenario=scenario,
        )
        return JsonResponse({'session_id': session.id, 'redirect': f'/webapp/practice/session/{session.id}/'})

    return redirect('/webapp/practice/')


@webapp_login_required
def practice_session(request, session_id):
    from practice.models import PracticeSession
    session = get_object_or_404(PracticeSession, id=session_id, user=request.user)
    return render(request, 'webapp/practice_session.html', {
        'session': session,
        'scenario': session.scenario,
        'user': request.user,
    })


# ─── Leaderboard ──────────────────────────────────────────────────────────────

@webapp_login_required
def leaderboard(request):
    from users.models import User

    # Top 20 by total voice rooms (ended)
    top_users = User.objects.annotate(
        cnt_u1=Count(
            'voice_rooms_as_user1',
            filter=Q(voice_rooms_as_user1__status='ended')
        ),
        cnt_u2=Count(
            'voice_rooms_as_user2',
            filter=Q(voice_rooms_as_user2__status='ended')
        ),
        avg_rating=Avg('received_voice_ratings__rating'),
        rating_count=Count('received_voice_ratings', distinct=True),
    ).annotate(
        total_voice_rooms=ExpressionWrapper(
            F('cnt_u1') + F('cnt_u2'),
            output_field=IntegerField()
        )
    ).order_by('-total_voice_rooms')[:20]

    board = []
    for i, u in enumerate(top_users, 1):
        avg = round(u.avg_rating or 0, 1)
        board.append({
            'rank': i,
            'name': u.get_full_name() or u.username,
            'username': u.username,
            'total_rooms': u.total_voice_rooms,
            'avg_rating': avg,
            'rating_count': u.rating_count,
            'is_me': u == request.user,
            'is_premium': u.has_premium_active,
        })

    # My rank
    my_rank = next((b['rank'] for b in board if b['is_me']), None)

    return render(request, 'webapp/leaderboard.html', {
        'user': request.user,
        'board': board,
        'my_rank': my_rank,
    })


# ─── Premium ──────────────────────────────────────────────────────────────────

@webapp_login_required
def premium(request):
    from premium.models import PremiumPlan
    settings_obj = AppSettings.get()
    plans = PremiumPlan.objects.filter(is_active=True).order_by('order')
    card = PaymentCard.objects.filter(is_active=True).first()

    user = request.user
    referral_count = user.referrals.filter(
        referral_record__premium_granted=False
    ).count() if hasattr(user, 'referrals') else 0

    # Count actual referrals (users who registered with this user's ref code)
    from users.models import Referral
    ref_count = Referral.objects.filter(referrer=user).count()
    ref_premium_count = Referral.objects.filter(referrer=user, premium_granted=True).count()

    bot_username_cfg = getattr(settings, 'BOT_USERNAME', 'speaking_engbot')
    referral_link = f"https://t.me/{bot_username_cfg}?start=ref_{user.referral_code}"
    referrals_needed = settings_obj.referrals_for_premium
    premium_days = settings_obj.referral_premium_days

    features = [
        'Cheksiz speaking qo\'ng\'iroqlari',
        'Batafsil progress tahlili (AI)',
        'Barcha practice stsenariylari',
        'IELTS & CEFR mock testlar (cheksiz)',
        'Kunlik hisobot va daily plan',
        'Do\'st bilan ustuvor juftlash',
    ]

    first_plan = plans.first()
    plan_price_uzs = first_plan.price_uzs if first_plan else 49000

    return render(request, 'webapp/premium.html', {
        'user': user,
        'card': card,
        'ref_count': ref_count,
        'ref_premium_count': ref_premium_count,
        'referral_link': referral_link,
        'referrals_needed': referrals_needed,
        'premium_days': premium_days,
        'is_premium': user.has_premium_active,
        'premium_expires': user.premium_expires,
        'features': features,
        'plan_price_uzs': plan_price_uzs,
    })


@csrf_exempt
@webapp_login_required
@require_POST
def buy_premium(request, plan_id):
    """Record premium purchase request — bot deep link qaytaradi"""
    from premium.models import PremiumPlan, PremiumPurchase

    plan = get_object_or_404(PremiumPlan, id=plan_id, is_active=True)
    user = request.user

    card = PaymentCard.objects.filter(is_active=True).first()

    # Bot deep link (user botga o'tib chek yuboradi)
    bot_username = getattr(settings, 'BOT_USERNAME', '')
    bot_link = f"https://t.me/{bot_username}?start=buy_premium_{plan_id}" if bot_username else ''

    return JsonResponse({
        'ok': True,
        'plan_name': plan.name,
        'price_uzs': plan.price_uzs,
        'price_usd': str(plan.price_usd),
        'bot_link': bot_link,
        'card': {
            'number': card.card_number if card else '',
            'owner': card.owner_name if card else '',
            'bank': card.bank_name if card else '',
        } if card else None,
    })


# ─── Progress / AI Problems ───────────────────────────────────────────────────

def _notify_admin_premium_request(user, plan, purchase_id):
    """Telegram orqali adminga premium so'rov xabari yuborish"""
    try:
        import urllib.request as urlreq
        import urllib.parse as urlparse

        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        admin_ids_str = getattr(settings, 'ADMIN_CHAT_IDS', '')
        if not bot_token or not admin_ids_str:
            return

        username = f"@{user.username}" if user.username else str(user.telegram_id)
        text = (
            f"💰 <b>Yangi Premium So'rov (Web App)</b>\n\n"
            f"👤 <b>Foydalanuvchi:</b> {user.get_full_name() or user.username}\n"
            f"🆔 Telegram ID: <code>{user.telegram_id}</code>\n"
            f"📱 Username: {username}\n"
            f"📅 Reja: <b>{plan.name} — ${plan.price_usd}</b>\n"
            f"🔗 Purchase ID: {purchase_id}\n\n"
            f"⏳ Foydalanuvchi chekni botga yuboradi.\n"
            f"✅ Tasdiqlash: /grant_{user.telegram_id}_1"
        )

        for admin_id in admin_ids_str.split(','):
            admin_id = admin_id.strip()
            if not admin_id:
                continue
            try:
                data = urlparse.urlencode({
                    'chat_id': admin_id,
                    'text': text,
                    'parse_mode': 'HTML',
                }).encode()
                req = urlreq.Request(
                    f'https://api.telegram.org/bot{bot_token}/sendMessage',
                    data=data,
                )
                urlreq.urlopen(req, timeout=5)
            except Exception:
                pass
    except Exception:
        pass


def _check_bot_secret(request):
    """Verify BOT_SECRET header for bot API endpoints"""
    secret = request.META.get('HTTP_X_BOT_SECRET', '')
    return secret == getattr(settings, 'BOT_SECRET', 'speaking-bot-secret-key-2024')


@webapp_login_required
def progress(request):
    """Progress page with charts and AI daily plan — Premium only"""
    from ielts_mock.models import IELTSSession
    from cefr_mock.models import CEFRSession
    from practice.models import PracticeSession

    user = request.user

    # Premium bo'lmasa — premium sahifasiga yo'naltirish
    if not user.has_premium_active:
        return redirect('/webapp/premium/')


    ielts_sessions = list(IELTSSession.objects.filter(
        user=user, is_completed=True
    ).order_by('started_at').values(
        'overall_band', 'sub_scores', 'started_at',
        'strengths', 'improvements', 'mistakes', 'recommendations'
    ))

    cefr_sessions = list(CEFRSession.objects.filter(
        user=user, is_completed=True
    ).order_by('started_at').values('score', 'level', 'feedback', 'started_at'))

    practice_sessions_qs = PracticeSession.objects.filter(
        user=user, is_completed=True
    ).order_by('started_at')

    practice_sessions = list(practice_sessions_qs.values(
        'overall_score', 'grammar_score', 'vocab_score', 'fluency_score',
        'started_at', 'scenario__title'
    ))

    voice_rooms = VoiceRoom.objects.filter(
        Q(user1=user) | Q(user2=user), status='ended'
    ).count()

    # AI chat sessiyalar
    from chat.models import AIChat
    ai_chat_sessions = list(AIChat.objects.filter(
        user=user
    ).order_by('-created_at').values(
        'coach', 'message_count', 'analysis', 'created_at', 'ended_at'
    )[:20])

    ai_chat_data = []
    for s in ai_chat_sessions:
        ai_chat_data.append({
            'coach':         s.get('coach', ''),
            'messages':      s.get('message_count', 0),
            'analysis':      s.get('analysis', ''),
            'date':          s['created_at'].strftime('%d/%m/%Y') if s.get('created_at') else '',
        })

    # Format dates for JS charts
    ielts_data = []
    for s in ielts_sessions:
        if not s['overall_band']:
            continue
        sub = s.get('sub_scores') or {}
        ielts_data.append({
            'band':    float(s['overall_band']),
            'fluency': float(sub.get('fluency') or 0),
            'lexical': float(sub.get('lexical') or 0),
            'grammar': float(sub.get('grammar') or 0),
            'pronunciation': float(sub.get('pronunciation') or 0),
            'p1':   float(sub.get('part1_band') or 0),
            'p2':   float(sub.get('part2_band') or 0),
            'p3':   float(sub.get('part3_band') or 0),
            'date': s['started_at'].strftime('%d/%m/%Y'),
            'strengths':       (s.get('strengths') or [])[:3],
            'improvements':    (s.get('improvements') or [])[:3],
            'recommendations': (s.get('recommendations') or [])[:3],
        })

    cefr_data = []
    for s in cefr_sessions:
        if not s['score']:
            continue
        fb          = s.get('feedback') or {}
        part_scores = fb.get('part_scores') or {}
        cefr_data.append({
            'score':    s['score'],
            'level':    s['level'] or '',
            'fluency':  float(fb.get('fluency') or 0),
            'accuracy': float(fb.get('accuracy') or 0),
            'p1': int(part_scores.get('part1') or 0),
            'p2': int(part_scores.get('part2') or 0),
            'p3': int(part_scores.get('part3') or 0),
            'p4': int(part_scores.get('part4') or 0),
            'date':         s['started_at'].strftime('%d/%m/%Y'),
            'strengths':    (fb.get('strengths') or [])[:3],
            'improvements': (fb.get('improvements') or [])[:3],
            'summary':      fb.get('summary', ''),
        })
    practice_data = [
        {
            'score': s['overall_score'] or 0,
            'grammar': s['grammar_score'] or 0,
            'vocab': s['vocab_score'] or 0,
            'fluency': s['fluency_score'] or 0,
            'title': s['scenario__title'] or '',
            'date': s['started_at'].strftime('%d/%m'),
        }
        for s in practice_sessions if s['overall_score']
    ]

    # Average scores from analyzed practice sessions
    analyzed = [s for s in practice_sessions if s['overall_score']]
    avg_score = round(sum(s['overall_score'] for s in analyzed) / len(analyzed)) if analyzed else 0
    avg_grammar = round(sum((s['grammar_score'] or 0) for s in analyzed) / len(analyzed)) if analyzed else 0
    avg_vocab = round(sum((s['vocab_score'] or 0) for s in analyzed) / len(analyzed)) if analyzed else 0
    avg_fluency = round(sum((s['fluency_score'] or 0) for s in analyzed) / len(analyzed)) if analyzed else 0

    # Trend: compare last 3 vs previous 3
    score_trend = 0
    if len(practice_data) >= 4:
        recent = [s['score'] for s in practice_data[-3:]]
        older = [s['score'] for s in practice_data[-6:-3]]
        if older:
            score_trend = round(sum(recent) / len(recent) - sum(older) / len(older))

    # Daily plan from last analyzed practice session
    last_analyzed = PracticeSession.objects.filter(
        user=user, is_completed=True, analysis_done=True
    ).order_by('-started_at').first()

    daily_plan = []
    critical_thinking = ''
    if last_analyzed and last_analyzed.ai_feedback:
        fb = last_analyzed.ai_feedback
        daily_plan = fb.get('daily_plan') or []
        critical_thinking = fb.get('critical_thinking') or ''

    # Trigger analysis for any unanalyzed completed sessions (background)
    unanalyzed_ids = list(PracticeSession.objects.filter(
        user=user, is_completed=True, analysis_done=False
    ).values_list('id', flat=True)[:5])
    if unanalyzed_ids:
        try:
            from .tasks import analyze_practice_session
            for sid in unanalyzed_ids:
                analyze_practice_session.delay(sid)
        except Exception:
            pass

    # IELTS trend (oxirgi 3 vs oldingi 3)
    ielts_trend = 0
    if len(ielts_data) >= 4:
        r = [s['band'] for s in ielts_data[-3:]]
        o = [s['band'] for s in ielts_data[-6:-3]]
        if o:
            ielts_trend = round(sum(r)/len(r) - sum(o)/len(o), 1)

    # CEFR trend
    cefr_trend = 0
    if len(cefr_data) >= 4:
        r = [s['score'] for s in cefr_data[-3:]]
        o = [s['score'] for s in cefr_data[-6:-3]]
        if o:
            cefr_trend = round(sum(r)/len(r) - sum(o)/len(o))

    # Oxirgi IELTS session feedback
    last_ielts = ielts_data[-1] if ielts_data else {}
    last_cefr  = cefr_data[-1]  if cefr_data  else {}

    return render(request, 'webapp/progress.html', {
        'user': user,
        'ielts_data':       json.dumps(ielts_data),
        'cefr_data':        json.dumps(cefr_data),
        'practice_data':    json.dumps(practice_data),
        'voice_rooms_count': voice_rooms,
        'ielts_count':      len(ielts_data),
        'cefr_count':       len(cefr_data),
        'practice_count':   len(practice_data),
        'avg_score':        avg_score,
        'avg_grammar':      avg_grammar,
        'avg_vocab':        avg_vocab,
        'avg_fluency':      avg_fluency,
        'score_trend':      score_trend,
        'ielts_trend':      ielts_trend,
        'cefr_trend':       cefr_trend,
        'last_ielts':       last_ielts,
        'last_cefr':        last_cefr,
        'ai_chat_data':     json.dumps(ai_chat_data),
        'ai_chat_count':    len(ai_chat_data),
        'daily_plan':       json.dumps(daily_plan),
        'critical_thinking': critical_thinking,
        'is_premium':       user.has_premium_active,
    })

@webapp_login_required
def my_problems_ai(request):
    """AI sizning barcha natijalaringizni tahlil qiladi — history bilan"""
    user = request.user
    if not user.has_premium_active:
        return JsonResponse({'error': 'Premium talab qilinadi'}, status=403)

    from django.core.cache import cache
    from ielts_mock.models import IELTSSession
    from cefr_mock.models import CEFRSession
    from practice.models import PracticeSession
    from users.models import AIAdviceHistory, UserTenseStats
    import openai

    # Redis cache tekshirish (5 daqiqa)
    cache_key = f'ai_advice_{user.id}'
    cached = cache.get(cache_key)
    if cached:
        return JsonResponse({'ok': True, 'analysis': cached, 'from_cache': True})

    # ── Ma'lumotlarni yig'ish ──────────────────────────────────────────────────
    ielts_sessions = list(IELTSSession.objects.filter(
        user=user, is_completed=True
    ).order_by('-started_at')[:5].values(
        'overall_band', 'sub_scores', 'mistakes', 'improvements', 'started_at'
    ))

    cefr_sessions = list(CEFRSession.objects.filter(
        user=user, is_completed=True
    ).order_by('-started_at')[:5].values('score', 'level', 'feedback', 'started_at'))

    practice_sessions = list(PracticeSession.objects.filter(
        user=user, is_completed=True, analysis_done=True
    ).order_by('-started_at')[:7].values(
        'overall_score', 'grammar_score', 'vocab_score',
        'fluency_score', 'tense_stats', 'ai_feedback', 'started_at'
    ))

    feedbacks = list(user.received_voice_ratings.order_by(
        '-created_at'
    )[:10].values('rating', 'comment'))

    # ── Tense statistikasi (oxirgi 30 kun) ───────────────────────────────────
    from datetime import timedelta
    month_start = timezone.now().date() - timedelta(days=30)
    tense_qs = UserTenseStats.objects.filter(
        telegram_id=str(user.telegram_id), date__gte=month_start
    )
    tense_summary = {}
    for s in tense_qs:
        t = s.tense_name
        if t not in tense_summary:
            tense_summary[t] = {'usage': 0, 'correct': 0}
        tense_summary[t]['usage'] += s.usage_count
        tense_summary[t]['correct'] += s.correct_count
    tense_accuracy = {}
    for t, d in tense_summary.items():
        tense_accuracy[t] = round(d['correct'] / d['usage'] * 100) if d['usage'] > 0 else 0

    weak_tenses = {t: f"{pct}%" for t, pct in tense_accuracy.items() if pct < 70}
    strong_tenses = {t: f"{pct}%" for t, pct in tense_accuracy.items() if pct >= 80}

    # ── Oldingi maslahat tarixi (kontekst uchun) ─────────────────────────────
    prev_advice = list(AIAdviceHistory.objects.filter(user=user).order_by('-created_at')[:3].values(
        'context_summary', 'created_at'
    ))
    history_context = ""
    if prev_advice:
        history_lines = []
        for a in prev_advice:
            date_str = a['created_at'].strftime('%d.%m.%Y')
            history_lines.append(f"[{date_str}] {a['context_summary']}")
        history_context = "\n".join(history_lines)

    # ── AI Prompt ─────────────────────────────────────────────────────────────
    prompt = f"""You are an expert English language coach. Analyze this learner's data and give PERSONALIZED advice in ENGLISH.
IMPORTANT: Each advice must be different from previous ones. Build on progress, address NEW weaknesses.

PREVIOUS ADVICE HISTORY (do NOT repeat these):
{history_context or "No previous advice yet — this is the first analysis."}

CURRENT DATA:
IELTS Results (last 5): {json.dumps(ielts_sessions, default=str)}
CEFR Results (last 5): {json.dumps(cefr_sessions, default=str)}
Practice Sessions (last 7): {json.dumps(practice_sessions, default=str)}
Partner Ratings: {json.dumps(feedbacks, default=str)}
Tense Accuracy (30 days): {json.dumps(tense_accuracy)}
Weak Tenses (<70%): {json.dumps(weak_tenses)}
Strong Tenses (≥80%): {json.dumps(strong_tenses)}

Return ONLY valid JSON:
{{
  "problems": ["3-4 specific current problems based on data"],
  "exercises": ["Concrete daily exercises for each problem"],
  "timeline": "Realistic improvement timeline",
  "critical_thinking": "How to improve analytical thinking in English responses",
  "strengths": ["2-3 areas the learner is doing well"],
  "overall_advice": "1-2 sentence personalized summary based on their unique progress",
  "context_summary": "One sentence summarizing today's key advice (for next AI call context)"
}}"""

    try:
        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {'role': 'system', 'content': 'You are an expert English language coach. Always give fresh, personalized advice based on the learner\'s actual data.'},
                {'role': 'user', 'content': prompt}
            ],
            response_format={'type': 'json_object'},
            max_tokens=1200,
        )
        result = json.loads(response.choices[0].message.content)

        # Tarix sifatida saqlash
        AIAdviceHistory.objects.create(
            user=user,
            advice=result,
            context_summary=result.get('context_summary', '')
        )

        # Redis cache (5 daqiqa)
        cache.set(cache_key, result, 300)

        return JsonResponse({'ok': True, 'analysis': result})
    except Exception as e:
        logger.error(f"[my_problems_ai] error: {e}")
        return JsonResponse({'error': str(e)}, status=500)
# ─── Bot Admin API ────────────────────────────────────────────────────────────

@csrf_exempt
def bot_api_channels(request):
    """Bot admin: manage required channels"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    if request.method == 'GET':
        channels = list(RequiredChannel.objects.values(
            'id', 'channel_title', 'channel_username', 'channel_link',
            'is_active', 'is_bot_admin'
        ))
        return JsonResponse({'channels': channels})

    if request.method == 'POST':
        data = json.loads(request.body)
        action = data.get('action')

        if action == 'add':
            username = data.get('channel_username', '').lstrip('@')
            channel, created = RequiredChannel.objects.get_or_create(
                channel_username=username,
                defaults={
                    'channel_title': data.get('channel_title', username),
                    'channel_link': data.get('channel_link', f'https://t.me/{username}'),
                    'is_active': True,
                }
            )
            if not created:
                channel.is_active = True
                channel.save()
            return JsonResponse({'ok': True, 'created': created, 'id': channel.id})

        if action == 'remove':
            username = data.get('channel_username', '').lstrip('@')
            RequiredChannel.objects.filter(channel_username=username).update(is_active=False)
            return JsonResponse({'ok': True})

        if action == 'set_bot_admin':
            username = data.get('channel_username', '').lstrip('@')
            is_admin = data.get('is_bot_admin', False)
            RequiredChannel.objects.filter(channel_username=username).update(is_bot_admin=is_admin)
            return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def bot_api_stats(request):
    """Bot admin: get global stats"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from users.models import User
    from django.utils import timezone

    today = timezone.localdate()
    total = User.objects.count()
    premium = User.objects.filter(is_premium=True).count()
    today_active = User.objects.filter(last_seen__date=today).count()
    total_calls = VoiceRoom.objects.filter(status='ended').count()
    today_calls = VoiceRoom.objects.filter(status='ended', ended_at__date=today).count()

    settings_obj = AppSettings.get()

    return JsonResponse({
        'total_users': total,
        'premium_users': premium,
        'free_users': total - premium,
        'today_active': today_active,
        'total_calls': total_calls,
        'today_calls': today_calls,
        'free_calls_limit': settings_obj.free_calls_limit,
        'referrals_for_premium': settings_obj.referrals_for_premium,
    })


@csrf_exempt
def bot_api_cancel_premium(request):
    """Bot admin: cancel user's premium"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from users.models import User
    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')

    try:
        user = User.objects.get(telegram_id=telegram_id)
        user.is_premium = False
        user.premium_expires = None
        user.save(update_fields=['is_premium', 'premium_expires'])
        return JsonResponse({'ok': True, 'username': user.username})
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


@csrf_exempt
def bot_api_grant_premium(request):
    """Bot admin: grant premium to user by telegram_id"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from users.models import User
    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')
    days = int(data.get('days', 30))
    full_name = data.get('full_name', '')
    username = data.get('username', '') or f'tg_{telegram_id}'

    if not telegram_id:
        return JsonResponse({'error': 'telegram_id required'}, status=400)

    user, created = User.objects.get_or_create(
        telegram_id=telegram_id,
        defaults={
            'username': username,
            'first_name': full_name.split()[0] if full_name else '',
            'last_name': ' '.join(full_name.split()[1:]) if full_name and len(full_name.split()) > 1 else '',
        }
    )
    user.is_premium = True
    user.premium_expires = timezone.now() + timedelta(days=days)
    user.save(update_fields=['is_premium', 'premium_expires'])
    return JsonResponse({
        'ok': True,
        'username': user.username,
        'expires': user.premium_expires.isoformat(),
        'created': created,
    })


@csrf_exempt
def bot_api_settings(request):
    """Bot admin: get/update app settings"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    s = AppSettings.get()

    if request.method == 'GET':
        return JsonResponse({
            'free_calls_limit': s.free_calls_limit,
            'free_total_mock_limit': s.free_total_mock_limit,
            'free_ai_message_limit': s.free_ai_message_limit,
            'referrals_for_premium': s.referrals_for_premium,
            'referral_premium_days': s.referral_premium_days,
            'web_app_url': s.web_app_url,
        })

    if request.method == 'POST':
        data = json.loads(request.body)
        if 'free_calls_limit' in data:
            s.free_calls_limit = int(data['free_calls_limit'])
        if 'free_total_mock_limit' in data:
            s.free_total_mock_limit = int(data['free_total_mock_limit'])
        if 'free_ai_message_limit' in data:
            s.free_ai_message_limit = int(data['free_ai_message_limit'])
        if 'referrals_for_premium' in data:
            s.referrals_for_premium = int(data['referrals_for_premium'])
        if 'referral_premium_days' in data:
            s.referral_premium_days = int(data['referral_premium_days'])
        s.save()
        return JsonResponse({'ok': True})

    return JsonResponse({'error': 'Method not allowed'}, status=405)

# ─── WebSocket Token ──────────────────────────────────────────────────────────
# Bu funksiyani webapp/views.py faylining OXIRIGA qo'sh

@webapp_login_required
def ws_token(request):
    """
    WebSocket ulanish uchun bir martalik token yaratadi.
    Token 60 soniya amal qiladi va faqat bir marta ishlatiladi.
    """
    import hashlib
    import time
    from django.core.cache import cache

    token = hashlib.sha256(
        f"{request.user.id}:{time.time()}:{settings.SECRET_KEY}".encode()
    ).hexdigest()

    # Cache ga 60 soniya saqlaymiz
    cache.set(f"ws_token_{token}", request.user.id, timeout=60)

    return JsonResponse({'token': token})


# ─── Bot Premium API ──────────────────────────────────────────────────────────

@csrf_exempt
def bot_api_payment_card(request):
    """Bot: aktiv to'lov kartasi va 1 oylik narxni olish"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from premium.models import PremiumPlan

    card = PaymentCard.objects.filter(is_active=True).first()
    plan = PremiumPlan.objects.filter(is_active=True, duration_days=30).order_by('order').first()

    return JsonResponse({
        'card': {
            'number': card.card_number if card else '',
            'owner': card.owner_name if card else '',
            'bank': card.bank_name if card else '',
        } if card else None,
        'plan': {
            'id': plan.id,
            'name': plan.name,
            'price_uzs': plan.price_uzs,
            'duration_days': plan.duration_days,
        } if plan else None,
    })


@csrf_exempt
def bot_api_premium_request(request):
    """Bot: foydalanuvchi chek yuborilganda PremiumPurchase yaratish"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from premium.models import PremiumPlan, PremiumPurchase
    from users.models import User

    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')
    plan_id = data.get('plan_id')
    receipt_file_id = data.get('receipt_file_id', '')
    full_name = data.get('full_name', '')
    username = data.get('username', '')

    if not telegram_id or not receipt_file_id:
        return JsonResponse({'error': 'telegram_id and receipt_file_id required'}, status=400)

    # Plan olish
    if plan_id:
        plan = PremiumPlan.objects.filter(id=plan_id, is_active=True).first()
    else:
        plan = PremiumPlan.objects.filter(is_active=True, duration_days=30).order_by('order').first()
    if not plan:
        return JsonResponse({'error': 'No active plan found'}, status=404)

    # User olish (yoki yaratish)
    try:
        user = User.objects.get(telegram_id=telegram_id)
    except User.DoesNotExist:
        base_un = username.lower() if username else f"tg_{telegram_id}"
        final_un = base_un
        counter = 1
        while User.objects.filter(username=final_un).exists():
            final_un = f"{base_un}_{counter}"
            counter += 1
        name_parts = full_name.split(None, 1)
        user = User.objects.create_user(
            username=final_un,
            first_name=name_parts[0] if name_parts else full_name,
            last_name=name_parts[1] if len(name_parts) > 1 else '',
            telegram_id=telegram_id,
            password=None,
        )

    # PremiumPurchase yaratish
    purchase = PremiumPurchase.objects.create(
        user=user,
        plan=plan,
        telegram_username=username,
        telegram_id=telegram_id,
        receipt_file_id=receipt_file_id,
        status='pending',
    )

    return JsonResponse({
        'ok': True,
        'purchase_id': purchase.id,
        'plan_name': plan.name,
        'price_uzs': plan.price_uzs,
    })


@csrf_exempt
def bot_api_leaderboard(request):
    """Bot va Web: leaderboard top 30 + my_rank"""
    # Bot yoki login user — ikkalasi ham ko'ra oladi
    is_bot = _check_bot_secret(request)
    if not is_bot and not request.user.is_authenticated:
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from users.models import User
    from django.db.models import Avg, Count, Q, F, ExpressionWrapper, IntegerField

    sort_by = request.GET.get('sort_by', request.GET.get('sort', 'chat_count'))
    limit = min(int(request.GET.get('limit', 30)), 50)

    ALLOWED = ['chat_count', 'practice_count', 'ielts_count', 'cefr_count']
    if sort_by not in ALLOWED:
        sort_by = 'chat_count'

    # Barcha userlarni sort qilib olish
    qs = User.objects.filter(
        is_active=True,
        **{f'{sort_by}__gt': 0}
    ).annotate(
        avg_voice_rating=Avg('received_voice_ratings__rating'),
    ).order_by(f'-{sort_by}')

    all_ranked = list(qs)

    def user_to_dict(u, rank):
        avg = round(u.avg_voice_rating, 1) if u.avg_voice_rating else None
        photo_url = getattr(u, 'telegram_photo_url', None) or None
        return {
            'rank': rank,
            'id': u.id,
            'full_name': f"{u.first_name} {u.last_name}".strip() or u.username,
            'username': u.username or '',
            'photo_url': photo_url,
            'is_premium': getattr(u, 'has_premium_active', u.is_premium),
            'chat_count': u.chat_count or 0,
            'practice_count': u.practice_count or 0,
            'ielts_count': u.ielts_count or 0,
            'cefr_count': u.cefr_count or 0,
            'avg_rating': avg,
        }

    leaders_list = [user_to_dict(u, i + 1) for i, u in enumerate(all_ranked[:limit])]

    # My rank (faqat login user uchun)
    my_rank = None
    if request.user.is_authenticated:
        for i, u in enumerate(all_ranked):
            if u.id == request.user.id:
                my_rank = user_to_dict(u, i + 1)
                break

    return JsonResponse({
        'leaders': leaders_list,
        'leaderboard': leaders_list,  # bot eski formatni kutsa ham ishlaydi
        'my_rank': my_rank,
        'sort_by': sort_by,
        'total': len(leaders_list),
    })


@csrf_exempt
def bot_api_save_phone(request):
    """Bot: foydalanuvchi telefon raqamini saqlash"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from users.models import User
    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')
    phone = data.get('phone', '').strip()

    if not telegram_id or not phone:
        return JsonResponse({'error': 'telegram_id and phone required'}, status=400)

    updated = User.objects.filter(telegram_id=telegram_id).update(phone_number=phone)
    if not updated:
        return JsonResponse({'error': 'User not found'}, status=404)

    return JsonResponse({'ok': True, 'phone': phone})


@csrf_exempt
def bot_api_save_ielts(request):
    """Bot: IELTS natijasini DRF ga saqlash + Celery deep analysis trigger"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from ielts_mock.models import IELTSSession
    from users.models import User
    from django.utils import timezone

    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')
    band = data.get('band')
    sub_scores = data.get('sub_scores', {})
    feedback = data.get('feedback', {})
    answers = data.get('answers', [])  # [{question_id, question_text, part, transcript}]

    if not telegram_id or band is None:
        return JsonResponse({'error': 'telegram_id and band required'}, status=400)

    try:
        user = User.objects.get(telegram_id=telegram_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    # Q&A larni feedback ichida saqlash (keyinchalik Celery re-analyze uchun)
    feedback['qa_pairs'] = answers

    session = IELTSSession.objects.create(
        user=user,
        overall_band=band,
        sub_scores=sub_scores,
        strengths=feedback.get('strengths', []),
        improvements=feedback.get('improvements', []),
        mistakes=feedback.get('mistakes', []),
        recommendations=feedback.get('recommendations', []),
        is_completed=True,
        ended_at=timezone.now(),
    )
    # feedback ni to'liq saqlash (qa_pairs bilan)
    session.strengths = feedback.get('strengths', [])
    session.improvements = feedback.get('improvements', [])
    session.mistakes = feedback.get('mistakes', [])
    session.recommendations = feedback.get('recommendations', [])
    session.save(update_fields=['strengths', 'improvements', 'mistakes', 'recommendations'])

    user.ielts_count = (user.ielts_count or 0) + 1
    user.save(update_fields=['ielts_count'])

    # Agar Q&A pairs bo'lsa — Celery orqali per-part deep analysis qilish
    if answers:
        try:
            from .tasks import analyze_ielts_session_deep
            analyze_ielts_session_deep.delay(session.id, answers)
        except Exception:
            pass

    return JsonResponse({'ok': True, 'session_id': session.id, 'band': band})


@csrf_exempt
def bot_api_save_cefr(request):
    """Bot: CEFR natijasini DRF ga saqlash + Celery deep analysis trigger"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from cefr_mock.models import CEFRSession
    from users.models import User
    from django.utils import timezone

    data = json.loads(request.body)
    telegram_id = data.get('telegram_id')
    score = data.get('score')
    level = data.get('level')
    feedback = data.get('feedback', {})
    answers = data.get('answers', [])  # [{question_text, part, transcript}]

    if not telegram_id or score is None or not level:
        return JsonResponse({'error': 'telegram_id, score and level required'}, status=400)

    try:
        user = User.objects.get(telegram_id=telegram_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    # Q&A larni feedback ichida saqlash
    if answers:
        feedback['qa_pairs'] = answers

    session = CEFRSession.objects.create(
        user=user,
        score=score,
        level=level,
        feedback=feedback,
        is_completed=True,
        ended_at=timezone.now(),
    )
    user.cefr_count = (user.cefr_count or 0) + 1
    user.save(update_fields=['cefr_count'])

    # Per-part deep analysis (agar Q&A pairs bo'lsa)
    if answers:
        try:
            from .tasks import analyze_cefr_session_deep
            analyze_cefr_session_deep.delay(session.id, answers)
        except Exception:
            pass

    return JsonResponse({'ok': True, 'session_id': session.id, 'score': score, 'level': level})


@csrf_exempt
def bot_api_save_chat(request):
    """Bot: AI chat sessiyasini DRF ga saqlash"""
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    from chat.models import AIChat, AIChatMessage
    from users.models import User
    from django.utils import timezone

    data = json.loads(request.body)
    telegram_id   = data.get('telegram_id')
    coach         = data.get('coach', '')          # 'alex' yoki 'emma'
    messages      = data.get('messages', [])       # [{role, content}]
    analysis      = data.get('analysis', '')       # Sessiya tahlil matni
    tense_stats   = data.get('tense_stats', {})

    if not telegram_id:
        return JsonResponse({'error': 'telegram_id required'}, status=400)

    try:
        user = User.objects.get(telegram_id=telegram_id)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)

    # Faqat user + assistant xabarlar (system ni chiqarib tashlaymiz)
    real_messages = [m for m in messages if m.get('role') in ('user', 'assistant')]

    chat = AIChat.objects.create(
        user          = user,
        coach         = coach,
        message_count = len([m for m in real_messages if m.get('role') == 'user']),
        analysis      = analysis or '',
        tense_stats   = tense_stats or None,
        ended_at      = timezone.now(),
    )

    # Har bir xabarni saqlash
    AIChatMessage.objects.bulk_create([
        AIChatMessage(
            chat    = chat,
            role    = m['role'],
            content = m.get('content', '')[:2000],
        )
        for m in real_messages
    ])

    # User ai_chat_count yangilash
    if hasattr(user, 'ai_chat_count'):
        user.ai_chat_count = (user.ai_chat_count or 0) + 1
        user.save(update_fields=['ai_chat_count'])

    return JsonResponse({
        'ok': True,
        'chat_id': chat.id,
        'message_count': chat.message_count,
    })




@csrf_exempt
def bot_api_check_limit(request):
    if not _check_bot_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    from users.models import User

    telegram_id = request.GET.get('telegram_id')
    limit_type = request.GET.get('type', '')

    if not telegram_id:
        return JsonResponse({'error': 'telegram_id required'}, status=400)

    try:
        user = User.objects.get(telegram_id=telegram_id)
    except User.DoesNotExist:
        return JsonResponse({'allowed': True, 'used': 0, 'total': 999})

    if user.has_premium_active:
        return JsonResponse({'allowed': True, 'used': 0, 'total': 999, 'is_premium': True})

    s = AppSettings.get()

    if limit_type == 'speaking':
        from django.db.models import Q
        used = VoiceRoom.objects.filter(
            Q(user1=user) | Q(user2=user),
            partner_type='human', status='ended'
        ).count()
        total = s.free_calls_limit

    elif limit_type == 'ai_call':
        from django.db.models import Q
        used = VoiceRoom.objects.filter(
            Q(user1=user) | Q(user2=user),
            partner_type='ai', status='ended'
        ).count()
        total = s.free_ai_calls_limit

    elif limit_type == 'practice':
        from practice.models import PracticeSession
        used = PracticeSession.objects.filter(user=user, is_completed=True).count()
        total = s.free_practice_limit

    elif limit_type == 'ielts':
        from ielts_mock.models import IELTSSession
        used = IELTSSession.objects.filter(user=user, is_completed=True).count()
        total = s.free_ielts_limit

    elif limit_type == 'cefr':
        from cefr_mock.models import CEFRSession
        used = CEFRSession.objects.filter(user=user, is_completed=True).count()
        total = s.free_cefr_limit

    else:
        return JsonResponse({'allowed': True, 'used': 0, 'total': 999})

    return JsonResponse({
        'allowed': used < total,
        'used': used,
        'total': total,
        'is_premium': False,
    })

# ─── Vocabulary Chat API (webapp) ─────────────────────────────────────────────

@webapp_login_required
@csrf_exempt
def vocab_chat(request):
    """AI bilan so'z muhokamasi — text javob + TTS audio (base64)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    user = request.user

    # Limit tekshirish
    if not user.has_premium_active:
        s = AppSettings.get()
        if (user.ai_message_count or 0) >= s.free_ai_message_limit:
            return JsonResponse({'error': 'limit_reached'}, status=403)

    data = json.loads(request.body or '{}')
    word = data.get('word', '').strip()
    message = data.get('message', '').strip()
    history = data.get('history', [])

    if not word or not message:
        return JsonResponse({'error': 'word and message required'}, status=400)

    from openai import OpenAI
    import base64
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    # Build conversation
    system_prompt = (
        f'You are an English vocabulary coach helping the user understand the word "{word}". '
        f'Explain clearly, give examples, and answer questions about this word. '
        f'Keep responses short (2-3 sentences). Always speak in English.'
    )
    messages = [{'role': 'system', 'content': system_prompt}]
    for h in history[-8:]:
        messages.append({'role': h['role'], 'content': h['content']})
    messages.append({'role': 'user', 'content': message})

    # Text response
    resp = client.chat.completions.create(
        model='gpt-4o-mini',
        messages=messages,
        max_tokens=150,
    )
    ai_text = resp.choices[0].message.content

    # TTS audio
    audio_b64 = None
    try:
        tts = client.audio.speech.create(
            model='tts-1',
            voice='nova',
            input=ai_text,
            response_format='mp3',
        )
        audio_b64 = base64.b64encode(tts.content).decode()
    except Exception:
        pass

    # Increment message count
    user.ai_message_count = (user.ai_message_count or 0) + 1
    user.save(update_fields=['ai_message_count'])

    return JsonResponse({'text': ai_text, 'audio': audio_b64})


def another_view(request):
    return render(request, 'webapp/another.html')
