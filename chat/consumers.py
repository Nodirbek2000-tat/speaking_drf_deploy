import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        data = json.loads(text_data)
        message_type = data.get('type', 'message')

        if message_type == 'message':
            user = self.scope['user']
            if user.is_authenticated:
                msg = await self.save_message(user, data['content'])
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': data['content'],
                        'sender_id': user.id,
                        'sender_name': user.username,
                        'created_at': msg.created_at.isoformat(),
                    }
                )
        elif message_type == 'typing':
            user = self.scope['user']
            await self.channel_layer.group_send(
                self.room_group_name,
                {'type': 'typing_indicator', 'user_id': user.id, 'username': user.username}
            )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({'type': 'message', **event}))

    async def typing_indicator(self, event):
        await self.send(text_data=json.dumps({'type': 'typing', **event}))

    @database_sync_to_async
    def save_message(self, user, content):
        from .models import Message, ChatRoom
        room = ChatRoom.objects.get(id=self.room_id)
        return Message.objects.create(room=room, sender=user, content=content)


class MatchmakingConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        if not self.user.is_authenticated:
            await self.close()
            return
        await self.accept()
        await self.set_searching(True)
        partner = await self.find_partner()
        if partner:
            room = await self.create_room(partner)
            await self.channel_layer.group_send(
                f'user_{partner.id}',
                {'type': 'partner_found', 'room_id': room.id, 'partner': self.user.username}
            )
            await self.send(text_data=json.dumps({
                'type': 'matched',
                'room_id': room.id,
                'partner': partner.username
            }))
        else:
            await self.channel_layer.group_add(f'user_{self.user.id}', self.channel_name)
            await self.send(text_data=json.dumps({'type': 'searching'}))

    async def disconnect(self, close_code):
        await self.set_searching(False)
        await self.channel_layer.group_discard(f'user_{self.user.id}', self.channel_name)

    async def partner_found(self, event):
        await self.send(text_data=json.dumps({
            'type': 'matched',
            'room_id': event['room_id'],
            'partner': event['partner']
        }))

    @database_sync_to_async
    def set_searching(self, status):
        from users.models import User
        User.objects.filter(id=self.user.id).update(searching_partner=status, is_online=True)

    @database_sync_to_async
    def find_partner(self):
        from users.models import User
        return User.objects.filter(
            searching_partner=True, is_online=True
        ).exclude(id=self.user.id).first()

    @database_sync_to_async
    def create_room(self, partner):
        from .models import ChatRoom
        from users.models import User
        User.objects.filter(id__in=[self.user.id, partner.id]).update(searching_partner=False)
        User.objects.filter(id__in=[self.user.id, partner.id]).update(
            chat_count=__import__('django.db.models', fromlist=['F']).F('chat_count') + 1,
            free_searches_used=__import__('django.db.models', fromlist=['F']).F('free_searches_used') + 1,
        )
        return ChatRoom.objects.create(user1=self.user, user2=partner)
