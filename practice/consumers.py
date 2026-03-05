"""
PracticeSessionConsumer — Eng oddiy va ishonchli arxitektura

Eski muammo: server-side VAD chalkash, javoblar qovushib ketardi
Yangi yechim: Browser o'zi gapni yozadi, tugatganda 1 ta WebM audio yuboradi

Flow:
  1. Browser: MediaRecorder bilan yozadi, sukunat aniqlansa stop qiladi
  2. Browser: {"type": "audio", "data": "<base64 webm>"} yuboradi
  3. Server: Whisper → text → GPT-4o-mini → javob → TTS → MP3
  4. Server: MP3 ni binary + "ai_audio_done" yuboradi
  5. Browser: MP3 ni play qiladi

Token: ~$0.02 per 10 ta turn (Realtime API dan 50x arzon)
"""

import io
import json
import base64
import asyncio
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)

MAX_HISTORY = 8   # Token tejash


class PracticeSessionConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_obj = await self._get_session()
        if not self.session_obj:
            await self.close(code=4004)
            return

        await self.accept()

        self.chat_history  = []
        self.full_transcript = []
        self.processing    = False  # Bir vaqtda 1 ta request

        self.ai_prompt, self.scenario_title = await self._get_ai_prompt()
        logger.info(f'Practice connect: user={self.user.id} session={self.session_id}')

        # AI birinchi salom beradi
        await self._send_greeting()

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        data = json.loads(text_data)
        msg_type = data.get('type')

        if msg_type == 'audio':
            # Browser to'liq gapni yubordi
            if self.processing:
                # Hozir band — ignore
                await self.send(text_data=json.dumps({'type': 'busy'}))
                return
            audio_b64 = data.get('data', '')
            if audio_b64:
                self.processing = True
                asyncio.create_task(self._process_audio(audio_b64))

        elif msg_type == 'end':
            feedback = await self._generate_feedback()
            await self._complete_session(feedback)
            await self.send(text_data=json.dumps({
                'type': 'feedback',
                'data': feedback,
            }))

    # ── Audio processing pipeline ─────────────────────────────────────

    async def _process_audio(self, audio_b64: str):
        try:
            # 1. Whisper STT
            transcript = await self._stt(audio_b64)
            if not transcript or len(transcript.strip()) < 2:
                self.processing = False
                await self.send(text_data=json.dumps({'type': 'ready'}))
                return

            # User gapini ko'rsat
            await self.send(text_data=json.dumps({
                'type': 'user_transcript',
                'text': transcript,
            }))
            await self._save_message('user', transcript)
            self.full_transcript.append({'role': 'user', 'content': transcript})

            # 2. GPT javob
            ai_text = await self._gpt_response(transcript)
            if not ai_text:
                self.processing = False
                await self.send(text_data=json.dumps({'type': 'ready'}))
                return

            await self.send(text_data=json.dumps({
                'type': 'ai_text',
                'text': ai_text,
            }))
            await self._save_message('assistant', ai_text)
            self.full_transcript.append({'role': 'assistant', 'content': ai_text})

            # 3. TTS → MP3
            mp3 = await self._tts(ai_text)
            if mp3:
                await self.send(bytes_data=mp3)
            await self.send(text_data=json.dumps({'type': 'ai_done'}))

        except Exception as e:
            logger.error(f'_process_audio error: {e}')
            await self.send(text_data=json.dumps({'type': 'ready'}))
        finally:
            self.processing = False

    # ── Greeting ──────────────────────────────────────────────────────

    async def _send_greeting(self):
        """AI birinchi 1 ta qisqa gap bilan boshlaydi"""
        try:
            messages = [
                {'role': 'system', 'content': self.ai_prompt},
                {'role': 'user', 'content': 'Begin. One sentence only.'},
            ]
            greeting = await self._chat_completion(messages, max_tokens=40)
            if not greeting:
                greeting = "Hello! Ready to practice?"

            await self.send(text_data=json.dumps({'type': 'ai_text', 'text': greeting}))
            await self._save_message('assistant', greeting)
            self.full_transcript.append({'role': 'assistant', 'content': greeting})
            self.chat_history.append({'role': 'assistant', 'content': greeting})

            mp3 = await self._tts(greeting)
            if mp3:
                await self.send(bytes_data=mp3)
            await self.send(text_data=json.dumps({'type': 'ai_done'}))

        except Exception as e:
            logger.error(f'_send_greeting error: {e}')
            await self.send(text_data=json.dumps({'type': 'ready'}))

    # ── GPT ───────────────────────────────────────────────────────────

    async def _gpt_response(self, user_text: str) -> str:
        self.chat_history.append({'role': 'user', 'content': user_text})
        history = self.chat_history[-MAX_HISTORY:]

        system = (
            self.ai_prompt +
            '\n\nRules: 1) Max 1-2 short sentences. '
            '2) End with a question. '
            '3) Model correct grammar naturally. '
            '4) Stay in character.'
        )

        messages = [{'role': 'system', 'content': system}] + history
        reply = await self._chat_completion(messages, max_tokens=80)
        if reply:
            self.chat_history.append({'role': 'assistant', 'content': reply})
        return reply

    async def _chat_completion(self, messages: list, max_tokens: int = 80) -> str:
        import openai
        from django.conf import settings
        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.7,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            logger.error(f'GPT error: {e}')
            return ''

    # ── STT ───────────────────────────────────────────────────────────

    async def _stt(self, audio_b64: str) -> str:
        """Base64 audio → ffmpeg → WAV → Whisper → text"""
        import openai, tempfile, os, subprocess, shutil
        from django.conf import settings
        try:
            audio_bytes = base64.b64decode(audio_b64)
            logger.info(f'STT: audio size={len(audio_bytes)} bytes')

            if len(audio_bytes) < 3000:
                logger.warning('STT: audio too small, skip')
                return ''

            # ffmpeg ni topamiz (Windows PATH muammosi)
            ffmpeg_cmd = shutil.which('ffmpeg') or 'ffmpeg'
            logger.info(f'STT: ffmpeg path = {ffmpeg_cmd}')

            with tempfile.NamedTemporaryFile(suffix='.webm', delete=False) as f:
                f.write(audio_bytes)
                inp = f.name
            out = inp.replace('.webm', '.wav')

            try:
                proc = subprocess.run(
                    [ffmpeg_cmd, '-y', '-i', inp, '-ar', '16000', '-ac', '1', '-f', 'wav', out],
                    capture_output=True, timeout=15
                )
                if proc.returncode != 0 or not os.path.exists(out):
                    logger.error(f'ffmpeg failed: {proc.stderr.decode()[-300:]}')
                    return ''

                with open(out, 'rb') as f:
                    wav_bytes = f.read()
            finally:
                for p in [inp, out]:
                    try: os.unlink(p)
                    except: pass

            audio_file = io.BytesIO(wav_bytes)
            audio_file.name = 'speech.wav'

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            result = await client.audio.transcriptions.create(
                model='whisper-1',
                file=audio_file,
                language='en',
            )
            text = result.text.strip()
            logger.info(f'STT result: "{text}"')
            return text
        except Exception as e:
            logger.error(f'STT error: {e}')
            return ''

    # ── TTS ───────────────────────────────────────────────────────────

    async def _tts(self, text: str) -> bytes:
        """text → OpenAI TTS → MP3"""
        import openai
        from django.conf import settings
        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.audio.speech.create(
                model='tts-1',
                voice='alloy',
                input=text,
                response_format='mp3',
            )
            return resp.content
        except Exception as e:
            logger.error(f'TTS error: {e}')
            return b''

    # ── Feedback ─────────────────────────────────────────────────────

    async def _generate_feedback(self) -> dict:
        import openai
        from django.conf import settings

        user_lines = [m['content'] for m in self.full_transcript if m['role'] == 'user']
        if not user_lines:
            return _empty_feedback()

        conversation = '\n'.join(
            f"{'User' if m['role']=='user' else 'AI'}: {m['content']}"
            for m in self.full_transcript
        )

        prompt = f"""Analyze this English practice conversation. Return ONLY JSON.

Conversation:
{conversation}

JSON:
{{
  "score": 0-100,
  "grammar_score": 0-100,
  "vocab_score": 0-100,
  "fluency_score": 0-100,
  "strengths": ["...", "..."],
  "improvements": ["...", "..."],
  "mistakes": [{{"wrong":"...","correct":"...","explanation":"..."}}],
  "overall_comment": "1-2 sentences",
  "daily_plan": ["task1","task2","task3"],
  "critical_thinking": "advice",
  "tense_stats": {{"Present Simple":{{"total":0,"correct":0,"percent":0}}}}
}}"""

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': prompt}],
                response_format={'type': 'json_object'},
                max_tokens=700,
            )
            return json.loads(resp.choices[0].message.content)
        except Exception as e:
            logger.error(f'Feedback error: {e}')
            return _empty_feedback()

    # ── DB ────────────────────────────────────────────────────────────

    @database_sync_to_async
    def _get_session(self):
        from practice.models import PracticeSession
        try:
            s = PracticeSession.objects.select_related('scenario').get(
                id=self.session_id, user=self.user
            )
            return None if s.is_completed else s
        except PracticeSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_ai_prompt(self):
        sc = self.session_obj.scenario
        return sc.ai_prompt, sc.title

    @database_sync_to_async
    def _save_message(self, role, content):
        from practice.models import PracticeMessage
        try:
            PracticeMessage.objects.create(
                session=self.session_obj, role=role, content=content
            )
        except Exception as e:
            logger.warning(f'save_message: {e}')

    @database_sync_to_async
    def _complete_session(self, feedback):
        try:
            s = self.session_obj
            s.is_completed     = True
            s.ended_at         = timezone.now()
            s.ai_feedback      = feedback
            s.overall_score    = feedback.get('score')
            s.grammar_score    = feedback.get('grammar_score')
            s.vocab_score      = feedback.get('vocab_score')
            s.fluency_score    = feedback.get('fluency_score')
            s.tense_stats      = feedback.get('tense_stats') or {}
            s.analysis_done    = True
            s.duration_seconds = int((timezone.now() - s.started_at).total_seconds())
            s.save()
            u = s.user
            u.practice_count = (u.practice_count or 0) + 1
            u.save(update_fields=['practice_count'])
        except Exception as e:
            logger.error(f'complete_session: {e}')


def _empty_feedback():
    return {
        'score': 0, 'grammar_score': 0, 'vocab_score': 0, 'fluency_score': 0,
        'strengths': [], 'improvements': [], 'mistakes': [],
        'overall_comment': 'No speech detected.',
        'daily_plan': [], 'critical_thinking': '', 'tense_stats': {},
    }