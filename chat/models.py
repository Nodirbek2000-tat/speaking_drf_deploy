from django.db import models
from django.conf import settings


class ChatRoom(models.Model):
    STATUS_CHOICES = [('active', 'Active'), ('ended', 'Ended')]

    user1 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rooms_as_user1')
    user2 = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='rooms_as_user2')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Chat Room'
        verbose_name_plural = 'Chat Rooms'
        ordering = ['-started_at']

    def __str__(self):
        return f"{self.user1} ↔ {self.user2}"


class Message(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.sender}: {self.content[:40]}"


class ChatRating(models.Model):
    room = models.ForeignKey(ChatRoom, on_delete=models.CASCADE, related_name='ratings')
    rater = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='given_ratings')
    rated_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_ratings')
    rating = models.PositiveSmallIntegerField()  # 1-5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('room', 'rater')

    def __str__(self):
        return f"{self.rater} rated {self.rated_user}: {self.rating}/5"


class AIChat(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='ai_chats')
    created_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']


class AIChatMessage(models.Model):
    ROLE_CHOICES = [('user', 'User'), ('assistant', 'Assistant')]
    chat = models.ForeignKey(AIChat, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
