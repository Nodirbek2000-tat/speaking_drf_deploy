"""
Celery tasks — async background jobs:
- save_ai_message: AI suhbat xabarini DB ga saqlash
- analyze_ai_conversation: Suhbat tugagach AI tahlil qilish
"""
import logging
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=5)
def save_ai_message(self, room_id: int, role: str, content: str):
    """AI suhbat xabarini DB ga async saqlash"""
    try:
        from .models import AIMessage, VoiceRoom
        room = VoiceRoom.objects.get(id=room_id)
        AIMessage.objects.create(room=room, role=role, content=content)
    except Exception as exc:
        logger.error(f"[save_ai_message] room={room_id} error: {exc}")
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def analyze_ai_conversation(self, room_id: int, user_id: int):
    """
    Suhbat tugagandan so'ng AI tahlil:
    - Tense xatolari
    - Vocabulary saviyasi
    - Speaking fluency
    Natija VoiceRoom.ai_feedback ga saqlanadi (agar field bo'lsa)
    """
    try:
        import openai
        from django.conf import settings
        from .models import AIMessage, VoiceRoom

        room = VoiceRoom.objects.get(id=room_id)
        messages = AIMessage.objects.filter(room=room).order_by('created_at')

        if not messages.exists():
            return {'status': 'no_messages'}

        conversation = '\n'.join(
            f"{'User' if m.role == 'user' else 'AI'}: {m.content}"
            for m in messages
        )

        prompt = (
            "Analyze this English speaking conversation and give feedback in Uzbek.\n\n"
            f"Conversation:\n{conversation}\n\n"
            "Return JSON with keys:\n"
            "- score (0-100)\n"
            "- strengths (2-3 ta kuchli tomonlar)\n"
            "- improvements (2-3 ta yaxshilash kerak bo'lgan tomonlar)\n"
            "- grammar_mistakes (aniq grammatika xatolari va to'g'ri varianti)\n"
            "- tense_usage (qaysi zamonlarni ishlatdi va qanchalik to'g'ri)\n"
            "- overall_comment (1-2 jumlada umumiy baho)"
        )

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            max_tokens=600,
        )

        import json
        feedback = json.loads(resp.choices[0].message.content)

        # VoiceRoom ga feedback saqlash uchun field qo'shish mumkin,
        # hozircha log ga yozamiz
        logger.info(f"[analyze_ai_conversation] room={room_id} score={feedback.get('score')}")

        # Foydalanuvchiga Telegram orqali xabar yuborish (ixtiyoriy)
        _notify_user_feedback(user_id, feedback)

        return feedback

    except Exception as exc:
        logger.error(f"[analyze_ai_conversation] room={room_id} error: {exc}")
        raise self.retry(exc=exc)


def _notify_user_feedback(user_id: int, feedback: dict):
    """Foydalanuvchiga Telegram orqali suhbat tahlilini yuborish"""
    try:
        from users.models import User
        from django.conf import settings
        import urllib.request as urlreq
        import urllib.parse as urlparse

        user = User.objects.get(id=user_id)
        if not user.telegram_id:
            return

        bot_token = settings.TELEGRAM_BOT_TOKEN
        if not bot_token:
            return

        score = feedback.get('score', 0)
        strengths = feedback.get('strengths', [])
        improvements = feedback.get('improvements', [])
        comment = feedback.get('overall_comment', '')

        strengths_text = '\n'.join(f"  ✅ {s}" for s in strengths[:3])
        improvements_text = '\n'.join(f"  📌 {i}" for i in improvements[:3])

        text = (
            f"📊 <b>AI Suhbat Tahlili</b>\n\n"
            f"🎯 Ball: <b>{score}/100</b>\n\n"
            f"💪 <b>Kuchli tomonlar:</b>\n{strengths_text}\n\n"
            f"📈 <b>Yaxshilash kerak:</b>\n{improvements_text}\n\n"
            f"💬 {comment}"
        )

        data = urlparse.urlencode({
            'chat_id': user.telegram_id,
            'text': text,
            'parse_mode': 'HTML',
        }).encode()
        req = urlreq.Request(
            f'https://api.telegram.org/bot{bot_token}/sendMessage',
            data=data,
        )
        urlreq.urlopen(req, timeout=5)
    except Exception as e:
        logger.warning(f"[_notify_user_feedback] {e}")


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def analyze_practice_session(self, session_id: int):
    """
    Practice session ni Celery orqali chuqur tahlil qilish.
    analysis_done=False bo'lgan eski sessiyalar uchun ishlatiladi.
    """
    try:
        import json
        import openai
        from django.conf import settings
        from practice.models import PracticeSession, PracticeMessage

        session = PracticeSession.objects.select_related('scenario', 'user').get(
            id=session_id, is_completed=True, analysis_done=False
        )
        messages = PracticeMessage.objects.filter(session=session).order_by('created_at')

        if not messages.exists():
            session.analysis_done = True
            session.save(update_fields=['analysis_done'])
            return {'status': 'no_messages'}

        conversation = '\n'.join(
            f"{'User' if m.role == 'user' else 'AI'}: {m.content}"
            for m in messages
        )
        user_lines = [m.content for m in messages if m.role == 'user']

        prompt = (
            "You are an expert English speaking coach. Analyze this practice conversation.\n\n"
            f"Conversation:\n{conversation}\n\n"
            f"User's lines:\n" + '\n'.join(f'- {l}' for l in user_lines) + "\n\n"
            "Return ONLY valid JSON:\n"
            '{"score": <0-100>, "grammar_score": <0-100>, "vocab_score": <0-100>, '
            '"fluency_score": <0-100>, '
            '"tense_stats": {"Present Simple": {"total": 0, "correct": 0, "percent": 0}}, '
            '"strengths": ["..."], "improvements": ["..."], '
            '"mistakes": [{"wrong": "...", "correct": "...", "explanation": "..."}], '
            '"overall_comment": "...", '
            '"daily_plan": ["task1", "task2", "task3"], '
            '"critical_thinking": "advice on deeper analytical responses"}'
        )

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            max_tokens=700,
        )
        feedback = json.loads(resp.choices[0].message.content)

        session.overall_score = feedback.get('score')
        session.grammar_score = feedback.get('grammar_score')
        session.vocab_score = feedback.get('vocab_score')
        session.fluency_score = feedback.get('fluency_score')
        session.tense_stats = feedback.get('tense_stats') or {}
        session.ai_feedback = feedback
        session.analysis_done = True
        session.save(update_fields=[
            'overall_score', 'grammar_score', 'vocab_score', 'fluency_score',
            'tense_stats', 'ai_feedback', 'analysis_done'
        ])

        logger.info(f"[analyze_practice_session] session={session_id} score={feedback.get('score')}")
        return {'status': 'ok', 'score': feedback.get('score')}

    except PracticeSession.DoesNotExist:
        logger.warning(f"[analyze_practice_session] session={session_id} not found or already analyzed")
        return {'status': 'not_found'}
    except Exception as exc:
        logger.error(f"[analyze_practice_session] session={session_id} error: {exc}")
        raise self.retry(exc=exc)


@shared_task
def run_pending_practice_analyses():
    """
    Har 10 daqiqada ishga tushadi — analysis_done=False sessiyalarni topib tahlil qiladi.
    Celery beat schedule bilan ishlatiladi.
    """
    from practice.models import PracticeSession
    pending = PracticeSession.objects.filter(
        is_completed=True, analysis_done=False
    ).values_list('id', flat=True)[:20]

    count = 0
    for sid in pending:
        analyze_practice_session.delay(sid)
        count += 1

    logger.info(f"[run_pending_practice_analyses] queued {count} sessions")
    return {'queued': count}


@shared_task
def sync_user_phone(telegram_id: int, phone: str):
    """Bot dan kelgan telefon raqamini DRF User ga saqlash"""
    try:
        from users.models import User
        User.objects.filter(telegram_id=telegram_id).update(phone_number=phone)
        logger.info(f"[sync_user_phone] telegram_id={telegram_id} phone={phone}")
        return {'ok': True}
    except Exception as e:
        logger.error(f"[sync_user_phone] error: {e}")
        return {'ok': False, 'error': str(e)}


# ─── IELTS Deep Analysis ──────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def analyze_ielts_session_deep(self, session_id: int, qa_pairs: list):
    """
    IELTS sessiyasini har bir Part alohida baholash.
    qa_pairs: [{part, question_text, transcript}, ...]
    """
    try:
        import json
        import openai
        from django.conf import settings
        from ielts_mock.models import IELTSSession

        session = IELTSSession.objects.get(id=session_id)

        # Part bo'yicha guruhlash
        parts = {1: [], 2: [], 3: []}
        for qa in qa_pairs:
            p = int(qa.get('part', 1))
            if p in parts and qa.get('transcript'):
                parts[p].append(qa)

        # To'liq Q+A matn tuzish
        qa_text_lines = []
        for part_num in [1, 2, 3]:
            for qa in parts[part_num]:
                qa_text_lines.append(
                    f"[Part {part_num}] Q: {qa.get('question_text', 'Question')}\n"
                    f"A: {qa.get('transcript', '(no answer)')}"
                )

        if not qa_text_lines:
            return {'status': 'no_transcripts'}

        qa_text = '\n\n'.join(qa_text_lines)

        prompt = (
            "You are a STRICT IELTS Speaking examiner. Evaluate this test carefully.\n\n"
            + qa_text + "\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "overall_band": <float 1.0-9.0 in 0.5 steps>,\n'
            '  "part1_band": <float, Part 1 score>,\n'
            '  "part2_band": <float, Part 2 score>,\n'
            '  "part3_band": <float, Part 3 score>,\n'
            '  "sub_scores": {"fluency": <float>, "lexical": <float>, "grammar": <float>, "pronunciation": <float>},\n'
            '  "strengths": ["...", "..."],\n'
            '  "improvements": ["...", "..."],\n'
            '  "mistakes": [{"error": "...", "correction": "...", "explanation": "..."}],\n'
            '  "recommendations": ["...", "...", "..."],\n'
            '  "tense_stats": {"Present Simple": {"total": 0, "correct": 0, "percent": 0}},\n'
            '  "overall_comment": "1-2 sentence summary"\n'
            "}\n\n"
            "RULES: Band 9=native speaker. Band 7=minor errors. Band 5=noticeable errors. "
            "Uzbek/mixed language = reduce fluency 1-2 bands. Short answers = low score. "
            "Be brutally honest."
        )

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            max_tokens=1000,
        )
        result = json.loads(resp.choices[0].message.content)

        # Band ni normalize qilish
        def norm_band(v):
            try:
                b = float(v)
                return round(min(9.0, max(1.0, round(b * 2) / 2)), 1)
            except Exception:
                return 5.0

        overall = norm_band(result.get('overall_band', session.overall_band or 5.0))
        sub = result.get('sub_scores', {})
        # Per-part bandlarni sub_scores ga qo'shish
        sub['part1_band'] = norm_band(result.get('part1_band', overall))
        sub['part2_band'] = norm_band(result.get('part2_band', overall))
        sub['part3_band'] = norm_band(result.get('part3_band', overall))

        session.overall_band = overall
        session.sub_scores = sub
        session.strengths = result.get('strengths', session.strengths or [])
        session.improvements = result.get('improvements', session.improvements or [])
        session.mistakes = result.get('mistakes', session.mistakes or [])
        session.recommendations = result.get('recommendations', session.recommendations or [])
        session.save(update_fields=[
            'overall_band', 'sub_scores', 'strengths', 'improvements',
            'mistakes', 'recommendations'
        ])

        logger.info(f"[analyze_ielts_session_deep] session={session_id} band={overall}")
        return {'status': 'ok', 'band': overall}

    except IELTSSession.DoesNotExist:
        return {'status': 'not_found'}
    except Exception as exc:
        logger.error(f"[analyze_ielts_session_deep] session={session_id} error: {exc}")
        raise self.retry(exc=exc)


# ─── CEFR Deep Analysis ───────────────────────────────────────────────────────

@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def analyze_cefr_session_deep(self, session_id: int, qa_pairs: list):
    """
    CEFR sessiyasini har bir Part alohida baholash.
    qa_pairs: [{part, question_text, transcript}, ...]
    """
    try:
        import json
        import openai
        from django.conf import settings
        from cefr_mock.models import CEFRSession

        session = CEFRSession.objects.get(id=session_id)

        qa_text_lines = []
        for qa in qa_pairs:
            if qa.get('transcript'):
                qa_text_lines.append(
                    f"[Part {qa.get('part', '?')}] Q: {qa.get('question_text', 'Question')}\n"
                    f"A: {qa.get('transcript', '(no answer)')}"
                )

        if not qa_text_lines:
            return {'status': 'no_transcripts'}

        qa_text = '\n\n'.join(qa_text_lines)

        prompt = (
            "You are a STRICT CEFR Speaking examiner. Evaluate this test.\n\n"
            + qa_text + "\n\n"
            "Scoring: A1(1-14), A2(15-34), B1(35-50), B2(51-65), C1(66-75)\n"
            "Evaluate: Range, Accuracy, Fluency, Interaction, Coherence\n\n"
            "Return ONLY valid JSON:\n"
            "{\n"
            '  "score": <int 1-75>,\n'
            '  "level": <"A1"|"A2"|"B1"|"B2"|"C1">,\n'
            '  "part_scores": {"part1": <int 1-75>, "part2": <int 1-75>, "part3": <int 1-75>, "part4": <int 1-75>},\n'
            '  "range": <float 1-10>,\n'
            '  "accuracy": <float 1-10>,\n'
            '  "fluency": <float 1-10>,\n'
            '  "interaction": <float 1-10>,\n'
            '  "coherence": <float 1-10>,\n'
            '  "errors": [{"error": "...", "correction": "...", "explanation": "..."}],\n'
            '  "strengths": ["...", "..."],\n'
            '  "improvements": ["...", "..."],\n'
            '  "summary": "overall feedback 1-2 sentences"\n'
            "}\n\n"
            "RULES: Be brutally honest. Uzbek/mixed language = -5 to -10 points. "
            "Score 70+ = near native. Most learners score 30-55."
        )

        client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.chat.completions.create(
            model='gpt-4o-mini',
            messages=[{'role': 'user', 'content': prompt}],
            response_format={'type': 'json_object'},
            max_tokens=900,
        )
        result = json.loads(resp.choices[0].message.content)

        raw_score = int(result.get('score', session.score or 40))
        score = min(75, max(1, raw_score))

        # Level aniqlash
        if score <= 14: level = 'A1'
        elif score <= 34: level = 'A2'
        elif score <= 50: level = 'B1'
        elif score <= 65: level = 'B2'
        else: level = 'C1'

        # feedback ni yangilash
        existing_feedback = session.feedback or {}
        existing_feedback.update({
            'summary': result.get('summary', ''),
            'strengths': result.get('strengths', []),
            'improvements': result.get('improvements', []),
            'errors': result.get('errors', []),
            'part_scores': result.get('part_scores', {}),
            'range': result.get('range'),
            'accuracy': result.get('accuracy'),
            'fluency': result.get('fluency'),
            'interaction': result.get('interaction'),
            'coherence': result.get('coherence'),
        })

        session.score = score
        session.level = level
        session.feedback = existing_feedback
        session.save(update_fields=['score', 'level', 'feedback'])

        logger.info(f"[analyze_cefr_session_deep] session={session_id} score={score} level={level}")
        return {'status': 'ok', 'score': score, 'level': level}

    except CEFRSession.DoesNotExist:
        return {'status': 'not_found'}
    except Exception as exc:
        logger.error(f"[analyze_cefr_session_deep] session={session_id} error: {exc}")
        raise self.retry(exc=exc)


# ─── Daily Progress Report (har kuni 22:00) ───────────────────────────────────

@shared_task
def send_daily_progress_reports():
    """
    Har kuni 22:00 da barcha active userlarga Telegram progress xabari yuborish.
    Oxirgi 7 kun taqqoslanadi: o'sish yoki kamayish ko'rsatiladi.
    """
    import json
    import urllib.request as urlreq
    import urllib.parse as urlparse
    from django.conf import settings
    from django.utils import timezone
    from datetime import timedelta
    from users.models import User
    from ielts_mock.models import IELTSSession
    from cefr_mock.models import CEFRSession
    from practice.models import PracticeSession

    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        logger.warning("[daily_report] No bot token")
        return {'status': 'no_token'}

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    # Active userlar: oxirgi 7 kunda biror narsa qilgan
    active_users = User.objects.filter(
        telegram_id__isnull=False,
        last_activity__gte=week_ago
    ).exclude(telegram_id='')[:200]

    sent = 0
    for user in active_users:
        try:
            text = _build_daily_report(user, now, week_ago, two_weeks_ago)
            if not text:
                continue

            payload = urlparse.urlencode({
                'chat_id': user.telegram_id,
                'text': text,
                'parse_mode': 'HTML',
            }).encode()
            req = urlreq.Request(
                f'https://api.telegram.org/bot{bot_token}/sendMessage',
                data=payload,
            )
            urlreq.urlopen(req, timeout=5)
            sent += 1
        except Exception as e:
            logger.warning(f"[daily_report] user={user.telegram_id} error: {e}")

    logger.info(f"[daily_report] sent={sent}/{active_users.count()}")
    return {'status': 'ok', 'sent': sent}


def _build_daily_report(user, now, week_ago, two_weeks_ago) -> str:
    """Bir user uchun haftalik progress xabarini qurish"""
    from ielts_mock.models import IELTSSession
    from cefr_mock.models import CEFRSession
    from practice.models import PracticeSession

    lines = [f"📊 <b>{user.first_name or 'Salom'}, bugungi progress:</b>\n"]
    has_data = False

    # ── IELTS ─────────────────────────────────────────────────────────────────
    ielts_this = IELTSSession.objects.filter(
        user=user, is_completed=True, started_at__gte=week_ago
    ).order_by('-started_at')
    ielts_prev = IELTSSession.objects.filter(
        user=user, is_completed=True,
        started_at__gte=two_weeks_ago, started_at__lt=week_ago
    ).order_by('-started_at')

    if ielts_this.exists():
        has_data = True
        latest_ielts = ielts_this.first()
        band = latest_ielts.overall_band or 0
        lines.append(f"📝 <b>IELTS:</b> Band <b>{band}/9.0</b>")
        if ielts_prev.exists():
            prev_band = ielts_prev.first().overall_band or 0
            diff = round(band - prev_band, 1)
            if diff > 0:
                lines.append(f"   ↑ +{diff} o'sdi 🎉")
            elif diff < 0:
                lines.append(f"   ↓ {diff} kamaydi 📉")
            else:
                lines.append(f"   = O'zgarmadi ➡️")

        # Sub-scores
        sub = latest_ielts.sub_scores or {}
        if sub:
            p1 = sub.get('part1_band', '')
            p2 = sub.get('part2_band', '')
            p3 = sub.get('part3_band', '')
            if p1 or p2 or p3:
                parts_text = ' | '.join(filter(None, [
                    f"P1:{p1}" if p1 else '',
                    f"P2:{p2}" if p2 else '',
                    f"P3:{p3}" if p3 else '',
                ]))
                lines.append(f"   {parts_text}")
        lines.append("")

    # ── CEFR ──────────────────────────────────────────────────────────────────
    cefr_this = CEFRSession.objects.filter(
        user=user, is_completed=True, started_at__gte=week_ago
    ).order_by('-started_at')
    cefr_prev = CEFRSession.objects.filter(
        user=user, is_completed=True,
        started_at__gte=two_weeks_ago, started_at__lt=week_ago
    ).order_by('-started_at')

    if cefr_this.exists():
        has_data = True
        latest_cefr = cefr_this.first()
        score = latest_cefr.score or 0
        level = latest_cefr.level or '?'
        lines.append(f"🎓 <b>CEFR:</b> <b>{score}/75</b> ({level})")
        if cefr_prev.exists():
            prev_score = cefr_prev.first().score or 0
            diff = score - prev_score
            if diff > 0:
                lines.append(f"   ↑ +{diff} ball o'sdi 🎉")
            elif diff < 0:
                lines.append(f"   ↓ {diff} ball kamaydi 📉")
            else:
                lines.append(f"   = O'zgarmadi ➡️")
        lines.append("")

    # ── Practice ──────────────────────────────────────────────────────────────
    practice_this = PracticeSession.objects.filter(
        user=user, is_completed=True, started_at__gte=week_ago
    ).order_by('-started_at')

    if practice_this.exists():
        has_data = True
        count = practice_this.count()
        scores = [s for s in practice_this.values_list('overall_score', flat=True) if s]
        avg = round(sum(scores) / len(scores)) if scores else 0
        lines.append(f"🎤 <b>Practice:</b> {count} ta sessiya, o'rtacha <b>{avg}/100</b>")

        # Trend
        practice_prev = PracticeSession.objects.filter(
            user=user, is_completed=True,
            started_at__gte=two_weeks_ago, started_at__lt=week_ago
        )
        if practice_prev.exists():
            prev_scores = [s for s in practice_prev.values_list('overall_score', flat=True) if s]
            if prev_scores:
                prev_avg = round(sum(prev_scores) / len(prev_scores))
                diff = avg - prev_avg
                if diff > 0:
                    lines.append(f"   ↑ +{diff} ball o'sdi 🎉")
                elif diff < 0:
                    lines.append(f"   ↓ {diff} ball kamaydi 📉")
        lines.append("")

    if not has_data:
        return ""  # Hech qanday faollik yo'q — xabar yubormaymiz

    lines.append("💪 Har kuni mashq qiling — muvaffaqiyat sizniki!")
    lines.append("📱 <a href='https://t.me/tilchi_aibot'>Web App → My Progress</a>")

    return "\n".join(lines)
