from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.conf import settings
from openai import OpenAI
from .models import ChatRoom, Message, ChatRating, AIChat, AIChatMessage
from .serializers import ChatRoomSerializer, ChatRatingSerializer, AIChatSerializer, AIChatMessageSerializer


class MyChatRoomsView(generics.ListAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ChatRoom.objects.filter(
            user1=user
        ).union(ChatRoom.objects.filter(user2=user)).order_by('-started_at')


class ChatRoomDetailView(generics.RetrieveAPIView):
    serializer_class = ChatRoomSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        return ChatRoom.objects.filter(user1=user) | ChatRoom.objects.filter(user2=user)


class EndChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, room_id):
        try:
            room = ChatRoom.objects.get(id=room_id, status='active')
            if room.user1 != request.user and room.user2 != request.user:
                return Response({'error': 'Not your room'}, status=403)
            room.status = 'ended'
            room.ended_at = timezone.now()
            room.save()
            return Response({'status': 'ended'})
        except ChatRoom.DoesNotExist:
            return Response({'error': 'Room not found'}, status=404)


class RateChatView(generics.CreateAPIView):
    serializer_class = ChatRatingSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(rater=self.request.user)


class OnlineUsersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from users.models import User
        online = User.objects.filter(is_online=True).exclude(id=request.user.id)
        return Response([{'id': u.id, 'username': u.username, 'avatar': u.avatar.url if u.avatar else None} for u in online])


class StartAIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        chat = AIChat.objects.create(user=request.user)
        AIChatMessage.objects.create(
            chat=chat, role='assistant',
            content="Hi! I'm Alex, your English speaking coach. Let's practice English together! What would you like to talk about today?"
        )
        return Response(AIChatSerializer(chat).data)


class SendAIMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, chat_id):
        try:
            chat = AIChat.objects.get(id=chat_id, user=request.user)
        except AIChat.DoesNotExist:
            return Response({'error': 'Chat not found'}, status=404)

        user_message = request.data.get('content', '')
        if not user_message:
            return Response({'error': 'Content required'}, status=400)

        AIChatMessage.objects.create(chat=chat, role='user', content=user_message)

        messages = chat.messages.all()
        history = [
            {'role': 'system', 'content': """You are Alex, a friendly English speaking coach.
- Help users practice conversational English
- Gently correct mistakes inline in your response
- Encourage use of new vocabulary
- Keep responses concise (2-4 sentences)
- If user writes in another language, respond in English and ask them to try in English"""}
        ] + [{'role': m.role if m.role == 'user' else 'assistant', 'content': m.content} for m in messages]

        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model='gpt-4o-mini', messages=history, max_tokens=300
            )
            ai_reply = resp.choices[0].message.content
        except Exception as e:
            ai_reply = "Sorry, I had a small issue. Could you repeat that?"

        msg = AIChatMessage.objects.create(chat=chat, role='assistant', content=ai_reply)
        return Response(AIChatMessageSerializer(msg).data)


class MyAIChatsView(generics.ListAPIView):
    serializer_class = AIChatSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AIChat.objects.filter(user=self.request.user)
