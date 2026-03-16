"""
WebSocket consumers:
- VoiceMatchmakingConsumer: find speaking partner
- VoiceCallConsumer: WebRTC signaling (offer/answer/ICE)
- AICallConsumer: OpenAI Realtime API proxy (ultra-low latency)
"""
import json
import asyncio
import base64
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)

_search_queue: dict = {}

GEMINI_LIVE_MODEL = 'gemini-2.0-flash-live-001'


# ─── VoiceMatchmakingConsumer ──────────────────────────────────────────────────

class VoiceMatchmakingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user.is_authenticated:
            _search_queue.pop(self.user.id, None)
            await self._update_searching(False)

    async def receive(self, text_data):
        data = json.loads(text_data)
        t = data.get('type')
        if t == 'search':
            await self._handle_search(data)
        elif t == 'cancel':
            _search_queue.pop(self.user.id, None)
            await self._update_searching(False)
            await self.send(json.dumps({'type': 'cancelled'}))

    async def _handle_search(self, data):
        gender_filter = data.get('gender_filter', 'any')
        level = data.get('level', 'any')
        name = (self.user.first_name or self.user.username).strip()
        _search_queue[self.user.id] = {
            'channel_name': self.channel_name,
            'gender_filter': gender_filter,
            'level': level,
            'user_id': self.user.id,
            'name': name,
            'username': self.user.username,
        }
        await self._update_searching(True)
        partner = self._find_match(gender_filter, level)
        if partner:
            _search_queue.pop(self.user.id, None)
            _search_queue.pop(partner['user_id'], None)
            room = await self._create_voice_room(partner['user_id'], gender_filter, level)
            await self.channel_layer.send(
                partner['channel_name'],
                {
                    'type': 'match_found',
                    'room_id': room.id,
                    'role': 'callee',
                    'partner': {'name': name, 'username': self.user.username},
                }
            )
            await self.send(json.dumps({
                'type': 'matched',
                'room_id': room.id,
                'role': 'caller',
                'partner': {'name': partner['name'], 'username': partner['username']},
            }))
        else:
            await self.send(json.dumps({'type': 'searching'}))

    def _find_match(self, gender_filter, level):
        for uid, info in list(_search_queue.items()):
            if uid == self.user.id:
                continue
            if level != 'any' and info['level'] != 'any' and info['level'] != level:
                continue
            return info
        return None

    async def match_found(self, event):
        await self.send(json.dumps({
            'type': 'matched',
            'room_id': event['room_id'],
            'role': event['role'],
            'partner': event['partner'],
        }))

    @database_sync_to_async
    def _create_voice_room(self, partner_id, gender_filter, level):
        from .models import VoiceRoom
        from users.models import User
        from django.db.models import F
        partner = User.objects.get(id=partner_id)
        room = VoiceRoom.objects.create(
            user1=self.user, user2=partner,
            partner_type='human', status='active',
            gender_filter=gender_filter, level=level,
            connected_at=timezone.now(),
        )
        User.objects.filter(id__in=[self.user.id, partner_id]).update(chat_count=F('chat_count') + 1)
        return room

    @database_sync_to_async
    def _update_searching(self, searching):
        from users.models import User
        User.objects.filter(id=self.user.id).update(searching_partner=searching, is_online=True)


# ─── VoiceCallConsumer ─────────────────────────────────────────────────────────

class VoiceCallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.group = f'voice_{self.room_id}'
        await self.channel_layer.group_add(self.group, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        t = data.get('type')
        if t in ('offer', 'answer', 'ice_candidate'):
            await self.channel_layer.group_send(
                self.group,
                {'type': 'signal_forward', 'message': data, 'sender': self.channel_name}
            )
        elif t == 'end_call':
            await self._end_call()
            await self.channel_layer.group_send(
                self.group, {'type': 'call_ended', 'ended_by': self.user.username}
            )

    async def signal_forward(self, event):
        if event['sender'] != self.channel_name:
            await self.send(text_data=json.dumps(event['message']))

    async def call_ended(self, event):
        await self.send(text_data=json.dumps({'type': 'call_ended', 'ended_by': event['ended_by']}))

    @database_sync_to_async
    def _end_call(self):
        from .models import VoiceRoom
        try:
            room = VoiceRoom.objects.get(id=self.room_id)
            if room.status == 'active':
                duration = int((timezone.now() - (room.connected_at or room.started_at)).total_seconds())
                room.status = 'ended'
                room.ended_at = timezone.now()
                room.duration_seconds = duration
                room.save(update_fields=['status', 'ended_at', 'duration_seconds'])
        except VoiceRoom.DoesNotExist:
            pass


# ─── AICallConsumer — Gemini Live API proxy ───────────────────────────────────

class AICallConsumer(AsyncWebsocketConsumer):
    """
    Browser PCM16 audio → bizning server → Gemini 2.0 Flash Live API
    Gemini Live API PCM16 audio → bizning server → Browser

    Audio format: PCM16, 16kHz, mono (kirish)
                  PCM16, 24kHz, mono (chiqish — Gemini standart)
    """

    AI_INSTRUCTIONS = (
        'You are Alex, a friendly English speaking coach. '
        'Have natural conversations to help the user practice English. '
        'Rules: '
        '1) Keep every response to 1-2 short sentences maximum. '
        '2) Always end with a question to keep conversation flowing. '
        '3) When user makes a grammar mistake, naturally reuse the correct form in your reply without explicitly pointing it out. '
        '4) If user interrupts, stop immediately and listen. '
        '5) Be warm, encouraging, and never lecture. '
        '6) React naturally like a real conversation partner would.'
    )

    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()
        self.gemini_session  = None
        self._gemini_ctx     = None
        self.forward_task    = None
        self.room            = await self._create_room()

        try:
            await self._connect_gemini()
        except Exception as e:
            logger.error(f'AICallConsumer: Gemini connect failed: {e}')
            await self.send(text_data=json.dumps({
                'type': 'error', 'text': 'Could not connect to AI. Try again.'
            }))
            await self.close()

    async def disconnect(self, close_code):
        await self._cleanup()

    async def receive(self, text_data=None, bytes_data=None):
        # Browser PCM16 audio chunk → Gemini
        if bytes_data and self.gemini_session:
            try:
                from google.genai import types as gtypes
                await self.gemini_session.send(
                    input=gtypes.LiveClientRealtimeInput(
                        media_chunks=[gtypes.Blob(
                            data=bytes_data,
                            mime_type='audio/pcm;rate=16000',
                        )]
                    )
                )
            except Exception as e:
                logger.error(f'AICallConsumer.receive audio error: {e}')

        elif text_data:
            data = json.loads(text_data)
            if data.get('type') == 'end':
                await self._cleanup()
                await self.send(text_data=json.dumps({
                    'type': 'ended', 'room_id': self.room.id
                }))
                try:
                    from .tasks import analyze_ai_conversation
                    analyze_ai_conversation.delay(self.room.id, self.user.id)
                except Exception as e:
                    logger.warning(f'Celery task failed: {e}')

    # ── Gemini Live ulanish ────────────────────────────────────────────

    async def _connect_gemini(self):
        import google.genai as google_genai
        from google.genai import types as gtypes
        from django.conf import settings

        client = google_genai.Client(api_key=settings.GEMINI_API_KEY)

        config = gtypes.LiveConnectConfig(
            response_modalities=['AUDIO'],
            system_instruction=gtypes.Content(
                parts=[gtypes.Part(text=self.AI_INSTRUCTIONS)],
                role='user',
            ),
            speech_config=gtypes.SpeechConfig(
                voice_config=gtypes.VoiceConfig(
                    prebuilt_voice_config=gtypes.PrebuiltVoiceConfig(
                        voice_name='Aoede',   # Tabiiy ingliz ovozi
                    )
                )
            ),
        )

        self._gemini_ctx = client.aio.live.connect(
            model=GEMINI_LIVE_MODEL, config=config
        )
        self.gemini_session = await self._gemini_ctx.__aenter__()

        # AI birinchi salom bersin
        await self.gemini_session.send(
            input='Hello! Greet the user warmly and start the conversation.',
            end_of_turn=True,
        )

        # Javoblarni browserga yo'naltiruvchi background task
        self.forward_task = asyncio.create_task(self._forward_from_gemini())

    # ── Gemini → Browser ──────────────────────────────────────────────

    async def _forward_from_gemini(self):
        try:
            while True:
                turn = self.gemini_session.receive()
                async for response in turn:
                    # PCM16 audio → browser (binary)
                    if response.data:
                        await self.send(bytes_data=response.data)

                    # Text transcript → browser
                    if response.text:
                        await self.send(text_data=json.dumps({
                            'type': 'ai_text_delta',
                            'text': response.text,
                        }))

                    # User transcription
                    sc = getattr(response, 'server_content', None)
                    if sc:
                        if getattr(sc, 'input_transcription', None):
                            txt = sc.input_transcription.text or ''
                            if txt.strip():
                                await self.send(text_data=json.dumps({
                                    'type': 'user_transcript',
                                    'text': txt.strip(),
                                }))
                                await self._save_msg_db('user', txt.strip())

                # Turn tugadi
                await self.send(text_data=json.dumps({'type': 'ai_audio_done'}))

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f'AICallConsumer._forward_from_gemini: {e}')

    # ── Cleanup ───────────────────────────────────────────────────────

    async def _cleanup(self):
        if self.forward_task:
            self.forward_task.cancel()
            try:
                await self.forward_task
            except asyncio.CancelledError:
                pass
        if self._gemini_ctx and self.gemini_session:
            try:
                await self._gemini_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self.gemini_session = None
        if hasattr(self, 'room'):
            await self._end_room()

    @database_sync_to_async
    def _save_msg_db(self, role: str, content: str):
        try:
            from .models import AIMessage
            AIMessage.objects.create(room=self.room, role=role, content=content)
        except Exception as e:
            logger.warning(f'_save_msg_db: {e}')

    @database_sync_to_async
    def _create_room(self):
        from .models import VoiceRoom
        return VoiceRoom.objects.create(
            user1=self.user,
            partner_type='ai',
            status='active',
            connected_at=timezone.now(),
        )

    @database_sync_to_async
    def _end_room(self):
        from .models import VoiceRoom
        try:
            room = VoiceRoom.objects.get(id=self.room.id)
            if room.status == 'active':
                duration = int((timezone.now() - (room.connected_at or room.started_at)).total_seconds())
                room.status = 'ended'
                room.ended_at = timezone.now()
                room.duration_seconds = duration
                room.save(update_fields=['status', 'ended_at', 'duration_seconds'])
        except VoiceRoom.DoesNotExist:
            pass