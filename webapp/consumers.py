"""
WebSocket consumers:
- VoiceMatchmakingConsumer: find speaking partner
- VoiceCallConsumer: WebRTC signaling (offer/answer/ICE)
- AICallConsumer: AI voice conversation
- PracticeSessionConsumer: AI practice session
"""
import json
import io
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone

logger = logging.getLogger(__name__)

# In-memory queue: {user_id: {channel_name, gender_filter, level, user_id, name, username}}
_search_queue: dict = {}


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

            my_name = name
            partner_name = partner['name']

            # Notify partner
            await self.channel_layer.send(
                partner['channel_name'],
                {
                    'type': 'match_found',
                    'room_id': room.id,
                    'role': 'callee',
                    'partner': {'name': my_name, 'username': self.user.username},
                }
            )

            # Notify self
            await self.send(json.dumps({
                'type': 'matched',
                'room_id': room.id,
                'role': 'caller',
                'partner': {'name': partner_name, 'username': partner['username']},
            }))
        else:
            await self.send(json.dumps({'type': 'searching'}))

    def _find_match(self, gender_filter, level):
        for uid, info in list(_search_queue.items()):
            if uid == self.user.id:
                continue
            # Level compatibility
            if level != 'any' and info['level'] != 'any' and info['level'] != level:
                continue
            return info
        return None

    async def match_found(self, event):
        """Channel layer message: partner found (for callee)"""
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
            user1=self.user,
            user2=partner,
            partner_type='human',
            status='active',
            gender_filter=gender_filter,
            level=level,
            connected_at=timezone.now(),
        )
        User.objects.filter(id__in=[self.user.id, partner_id]).update(
            chat_count=F('chat_count') + 1
        )
        return room

    @database_sync_to_async
    def _update_searching(self, searching):
        from users.models import User
        User.objects.filter(id=self.user.id).update(
            searching_partner=searching,
            is_online=True,
        )


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
            # Forward signaling to other peer
            await self.channel_layer.group_send(
                self.group,
                {
                    'type': 'signal_forward',
                    'message': data,
                    'sender': self.channel_name,
                }
            )
        elif t == 'end_call':
            await self._end_call()
            await self.channel_layer.group_send(
                self.group,
                {'type': 'call_ended', 'ended_by': self.user.username}
            )

    async def signal_forward(self, event):
        if event['sender'] != self.channel_name:
            await self.send(text_data=json.dumps(event['message']))

    async def call_ended(self, event):
        await self.send(text_data=json.dumps({
            'type': 'call_ended',
            'ended_by': event['ended_by'],
        }))

    @database_sync_to_async
    def _end_call(self):
        from .models import VoiceRoom
        try:
            room = VoiceRoom.objects.get(id=self.room_id)
            if room.status == 'active':
                conn_at = room.connected_at or room.started_at
                duration = int((timezone.now() - conn_at).total_seconds())
                room.status = 'ended'
                room.ended_at = timezone.now()
                room.duration_seconds = duration
                room.save(update_fields=['status', 'ended_at', 'duration_seconds'])
        except VoiceRoom.DoesNotExist:
            pass


class AICallConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            logger.warning('AICallConsumer: unauthenticated user, closing')
            await self.close(code=4001)
            return
        await self.accept()
        logger.info(f'AICallConsumer: user {self.user.id} connected')
        self.chat_history = []
        try:
            self.room = await self._create_room()
        except Exception as e:
            logger.error(f'AICallConsumer: _create_room failed: {e}')
            await self.send(text_data=json.dumps({'type': 'error', 'text': 'Server error. Please try again.'}))
            await self.close()
            return

        # Greeting
        greeting = await self._get_ai_response('Hello! I am ready to start our speaking practice.')
        await self.send(text_data=json.dumps({'type': 'ai_text', 'text': greeting}))
        audio = await self._tts(greeting)
        if audio:
            await self.send(bytes_data=audio)

    async def disconnect(self, close_code):
        if hasattr(self, 'room'):
            await self._end_room()

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            transcript = await self._stt(bytes_data)
            if transcript:
                await self.send(text_data=json.dumps({'type': 'user_transcript', 'text': transcript}))
                response = await self._get_ai_response(transcript)
                await self.send(text_data=json.dumps({'type': 'ai_text', 'text': response}))
                audio = await self._tts(response)
                if audio:
                    await self.send(bytes_data=audio)
        elif text_data:
            data = json.loads(text_data)
            if data.get('type') == 'end':
                await self._end_room()
                await self.send(text_data=json.dumps({'type': 'ended', 'room_id': self.room.id}))

    async def _get_ai_response(self, user_text: str) -> str:
        import openai
        from django.conf import settings

        self.chat_history.append({'role': 'user', 'content': user_text})
        messages = [
            {
                'role': 'system',
                'content': (
                    'You are Alex, a friendly and encouraging English speaking coach. '
                    'Have natural, engaging conversations to help the user practice speaking. '
                    'Gently correct major grammar mistakes. Keep responses concise (2-3 sentences max). '
                    'Encourage the user and ask follow-up questions.'
                )
            }
        ] + self.chat_history[-12:]

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages,
                max_tokens=150,
            )
            text = resp.choices[0].message.content
            self.chat_history.append({'role': 'assistant', 'content': text})
            return text
        except Exception as e:
            logger.error(f'AICallConsumer._get_ai_response error: {e}')
            return "I'm sorry, I had a small issue. Could you repeat that?"

    async def _stt(self, audio_bytes: bytes) -> str | None:
        import openai
        from django.conf import settings

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            audio_file = io.BytesIO(audio_bytes)
            # Detect format: WebM starts with EBML header 0x1A45DFA3
            audio_file.name = 'audio.webm' if audio_bytes[:4] == b'\x1a\x45\xdf\xa3' else 'audio.mp4'
            result = await client.audio.transcriptions.create(
                model='whisper-1',
                file=audio_file,
                language='en',
            )
            return result.text.strip() or None
        except Exception:
            return None

    async def _tts(self, text: str) -> bytes | None:
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
        except Exception:
            return None

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
                conn_at = room.connected_at or room.started_at
                duration = int((timezone.now() - conn_at).total_seconds())
                room.status = 'ended'
                room.ended_at = timezone.now()
                room.duration_seconds = duration
                room.save(update_fields=['status', 'ended_at', 'duration_seconds'])
        except VoiceRoom.DoesNotExist:
            pass


class PracticeSessionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            logger.warning('PracticeSessionConsumer: unauthenticated user, closing')
            await self.close(code=4001)
            return
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.session_obj = await self._get_session()
        if not self.session_obj:
            logger.warning(f'PracticeSessionConsumer: session {self.session_id} not found for user {self.user.id}')
            await self.close(code=4004)
            return
        await self.accept()
        logger.info(f'PracticeSessionConsumer: user {self.user.id} connected to session {self.session_id}')
        self.chat_history = []
        self.ai_prompt = await self._get_ai_prompt()

        # AI greeting
        greeting = await self._ai_greet()
        await self.send(text_data=json.dumps({'type': 'ai_text', 'text': greeting}))
        audio = await self._tts(greeting)
        if audio:
            await self.send(bytes_data=audio)

    async def disconnect(self, close_code):
        pass

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data:
            transcript = await self._stt(bytes_data)
            if transcript:
                await self._save_message('user', transcript)
                await self.send(text_data=json.dumps({'type': 'user_transcript', 'text': transcript}))
                response = await self._ai_respond(transcript)
                await self._save_message('assistant', response)
                await self.send(text_data=json.dumps({'type': 'ai_text', 'text': response}))
                audio = await self._tts(response)
                if audio:
                    await self.send(bytes_data=audio)
        elif text_data:
            data = json.loads(text_data)
            if data.get('type') == 'end':
                feedback = await self._generate_feedback()
                await self._complete_session(feedback)
                await self.send(text_data=json.dumps({'type': 'feedback', 'data': feedback}))

    async def _ai_greet(self) -> str:
        import openai
        from django.conf import settings

        messages = [
            {'role': 'system', 'content': self.ai_prompt},
            {'role': 'user', 'content': 'Hi, I am ready to start the practice session.'},
        ]
        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages,
                max_tokens=100,
            )
            text = resp.choices[0].message.content
            self.chat_history.append({'role': 'assistant', 'content': text})
            return text
        except Exception:
            return "Hello! Let's start our practice. Tell me about yourself."

    async def _ai_respond(self, user_text: str) -> str:
        import openai
        from django.conf import settings

        self.chat_history.append({'role': 'user', 'content': user_text})
        messages = [
            {'role': 'system', 'content': self.ai_prompt}
        ] + self.chat_history[-14:]

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model='gpt-4o-mini',
                messages=messages,
                max_tokens=150,
            )
            text = resp.choices[0].message.content
            self.chat_history.append({'role': 'assistant', 'content': text})
            return text
        except Exception:
            return "Interesting! Could you tell me more about that?"

    async def _generate_feedback(self) -> dict:
        import openai
        from django.conf import settings

        if not self.chat_history:
            return {'score': 0, 'strengths': [], 'improvements': [], 'mistakes': []}

        conversation = '\n'.join(
            f"{'User' if m['role'] == 'user' else 'AI'}: {m['content']}"
            for m in self.chat_history
        )

        prompt = f"""
Analyze this English speaking practice session and provide detailed feedback.

Conversation:
{conversation}

Return JSON with:
- score (0-100)
- strengths (list of 2-3 things done well)
- improvements (list of 2-3 areas to improve)
- mistakes (list of specific grammar/vocabulary mistakes with corrections)
- overall_comment (1-2 sentences summary)
"""
        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.chat.completions.create(
                model='gpt-4o-mini',
                messages=[{'role': 'user', 'content': prompt}],
                response_format={'type': 'json_object'},
                max_tokens=500,
            )
            import json
            return json.loads(resp.choices[0].message.content)
        except Exception:
            return {
                'score': 70,
                'strengths': ['Good effort!'],
                'improvements': ['Keep practicing'],
                'mistakes': [],
                'overall_comment': 'Great session! Keep it up.',
            }

    async def _stt(self, audio_bytes: bytes) -> str | None:
        import openai
        from django.conf import settings

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            audio_file = io.BytesIO(audio_bytes)
            # Detect format: WebM starts with EBML header 0x1A45DFA3
            audio_file.name = 'audio.webm' if audio_bytes[:4] == b'\x1a\x45\xdf\xa3' else 'audio.mp4'
            result = await client.audio.transcriptions.create(
                model='whisper-1',
                file=audio_file,
                language='en',
            )
            return result.text.strip() or None
        except Exception:
            return None

    async def _tts(self, text: str) -> bytes | None:
        import openai
        from django.conf import settings

        try:
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
            resp = await client.audio.speech.create(
                model='tts-1',
                voice='nova',
                input=text,
                response_format='mp3',
            )
            return resp.content
        except Exception:
            return None

    @database_sync_to_async
    def _get_session(self):
        from practice.models import PracticeSession
        try:
            s = PracticeSession.objects.select_related('scenario').get(
                id=self.session_id, user=self.user
            )
            if s.is_completed:
                return None
            return s
        except PracticeSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _get_ai_prompt(self) -> str:
        return self.session_obj.scenario.ai_prompt

    @database_sync_to_async
    def _save_message(self, role, content):
        from practice.models import PracticeMessage
        PracticeMessage.objects.create(
            session=self.session_obj,
            role=role,
            content=content,
        )

    @database_sync_to_async
    def _complete_session(self, feedback):
        from django.utils import timezone
        self.session_obj.is_completed = True
        self.session_obj.ended_at = timezone.now()
        self.session_obj.ai_feedback = feedback
        self.session_obj.overall_score = feedback.get('score')
        duration = (timezone.now() - self.session_obj.started_at).seconds
        self.session_obj.duration_seconds = duration
        self.session_obj.save()
