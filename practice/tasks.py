"""
practice/tasks.py — Celery orqali practice session tahlil qilish
"""
import logging
import json
from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def analyze_practice_session(self, session_id: int):
    """
    Practice session tugagandan so'ng Celery orqali AI tahlil qiladi.
    Natijalar: grammar, vocab, pronunciation, fluency, tense foizlari.
    """
    try:
        from practice.models import PracticeSession, PracticeMessage
        from openai import OpenAI
        from django.conf import settings

        session = PracticeSession.objects.select_related('scenario', 'user').get(id=session_id)

        if session.analysis_done:
            logger.info(f"Session {session_id} already analyzed")
            return

        # Barcha user xabarlarini yig'ish
        messages = PracticeMessage.objects.filter(session=session).order_by('created_at')
        user_texts = [m.content for m in messages if m.role == 'user']

        if not user_texts:
            logger.warning(f"Session {session_id}: no user messages")
            session.analysis_done = True
            session.save(update_fields=['analysis_done'])
            return

        full_transcript = "\n".join(f"User: {t}" for t in user_texts)

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        prompt = f"""Analyze this English speaking practice transcript and return JSON.

Transcript:
{full_transcript}

Return ONLY valid JSON with this exact structure:
{{
  "overall_score": 75,
  "grammar_score": 70,
  "vocab_score": 80,
  "pronunciation_score": 75,
  "fluency_score": 72,
  "tense_stats": {{
    "Present Simple": {{"total": 10, "correct": 8, "percent": 80}},
    "Present Continuous": {{"total": 5, "correct": 3, "percent": 60}},
    "Past Simple": {{"total": 8, "correct": 7, "percent": 87}},
    "Past Continuous": {{"total": 2, "correct": 1, "percent": 50}},
    "Present Perfect": {{"total": 3, "correct": 2, "percent": 67}},
    "Future Simple": {{"total": 4, "correct": 4, "percent": 100}}
  }},
  "grammar_errors": [
    {{"error": "I goed to shop", "correction": "I went to the shop", "explanation": "Irregular verb"}},
    {{"error": "She don't know", "correction": "She doesn't know", "explanation": "Subject-verb agreement"}}
  ],
  "vocab_feedback": "Good range of vocabulary. Try to use more academic words like 'consequently', 'furthermore'.",
  "pronunciation_feedback": "Clear pronunciation overall. Work on 'th' sounds and word stress.",
  "fluency_feedback": "Good flow with some hesitations. Reduce filler words like 'um', 'uh'.",
  "strengths": ["Good sentence variety", "Natural conversation flow", "Clear topic sentences"],
  "improvements": ["Work on irregular verbs", "Use more linking words", "Vary your tense usage"],
  "critical_thinking": "The student demonstrated basic reasoning but could develop arguments more deeply. Try to give specific examples to support your points.",
  "overall_feedback": "Overall good performance. Focus on grammar accuracy and vocabulary range."
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert English language examiner. Analyze speaking transcripts and provide detailed JSON feedback."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=1500,
        )

        result = json.loads(response.choices[0].message.content)

        # Session ga saqlash
        session.ai_feedback = result
        session.overall_score = result.get('overall_score', 70)
        session.grammar_score = result.get('grammar_score')
        session.vocab_score = result.get('vocab_score')
        session.pronunciation_score = result.get('pronunciation_score')
        session.fluency_score = result.get('fluency_score')
        session.tense_stats = result.get('tense_stats', {})
        session.analysis_done = True
        session.save(update_fields=[
            'ai_feedback', 'overall_score', 'grammar_score',
            'vocab_score', 'pronunciation_score', 'fluency_score',
            'tense_stats', 'analysis_done'
        ])

        # User statistikasini yangilash
        _update_user_stats(session)

        logger.info(f"Session {session_id} analyzed. Score: {session.overall_score}")
        return {'ok': True, 'session_id': session_id, 'score': session.overall_score}

    except PracticeSession.DoesNotExist:
        logger.error(f"Session {session_id} not found")
    except Exception as exc:
        logger.error(f"analyze_practice_session error: {exc}")
        raise self.retry(exc=exc)


def _update_user_stats(session):
    """User umumiy statistikasini yangilash"""
    try:
        user = session.user
        user.practice_count = (user.practice_count or 0) + 1
        user.save(update_fields=['practice_count'])
    except Exception as e:
        logger.warning(f"User stats update error: {e}")


@shared_task
def send_session_analysis_to_user(session_id: int, telegram_id: int):
    """
    Tahlil tayyor bo'lgandan so'ng foydalanuvchiga bot orqali xabar yuborish.
    (Ixtiyoriy — agar bot integration bo'lsa)
    """
    try:
        from practice.models import PracticeSession
        import aiohttp
        import asyncio
        from django.conf import settings

        session = PracticeSession.objects.get(id=session_id)
        if not session.ai_feedback:
            return

        fb = session.ai_feedback
        score = session.overall_score or 0

        text = (
            f"✅ <b>Amaliyot tahlili tayyor!</b>\n\n"
            f"📊 Umumiy ball: <b>{score:.0f}/100</b>\n\n"
            f"📝 Grammar: {session.grammar_score:.0f}/100\n"
            f"📚 Vocabulary: {session.vocab_score:.0f}/100\n"
            f"🗣 Fluency: {session.fluency_score:.0f}/100\n\n"
        )

        strengths = fb.get('strengths', [])
        if strengths:
            text += "✅ <b>Kuchli tomonlar:</b>\n"
            for s in strengths[:2]:
                text += f"• {s}\n"

        text += "\n📱 Batafsil tahlil uchun Web App → My Progress"

        # Bot API orqali yuborish
        bot_token = getattr(settings, 'TELEGRAM_BOT_TOKEN', '')
        if bot_token and telegram_id:
            import requests
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={
                    "chat_id": telegram_id,
                    "text": text,
                    "parse_mode": "HTML"
                },
                timeout=10
            )

    except Exception as e:
        logger.warning(f"send_session_analysis_to_user error: {e}")