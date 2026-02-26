from rest_framework import serializers
from .models import ChatRoom, Message, ChatRating, AIChat, AIChatMessage


class MessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source='sender.username', read_only=True)

    class Meta:
        model = Message
        fields = ['id', 'sender', 'sender_name', 'content', 'created_at']


class ChatRoomSerializer(serializers.ModelSerializer):
    user1_name = serializers.CharField(source='user1.username', read_only=True)
    user2_name = serializers.CharField(source='user2.username', read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ['id', 'user1', 'user1_name', 'user2', 'user2_name',
                  'status', 'started_at', 'ended_at', 'messages', 'last_message']

    def get_last_message(self, obj):
        last = obj.messages.last()
        return MessageSerializer(last).data if last else None


class ChatRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatRating
        fields = ['id', 'room', 'rated_user', 'rating', 'comment', 'created_at']
        read_only_fields = ['rater', 'created_at']


class AIChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = AIChatMessage
        fields = ['id', 'role', 'content', 'created_at']


class AIChatSerializer(serializers.ModelSerializer):
    messages = AIChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AIChat
        fields = ['id', 'created_at', 'ended_at', 'messages']
