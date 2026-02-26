from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/voice-match/$', consumers.VoiceMatchmakingConsumer.as_asgi()),
    re_path(r'ws/voice-call/(?P<room_id>\d+)/$', consumers.VoiceCallConsumer.as_asgi()),
    re_path(r'ws/ai-call/$', consumers.AICallConsumer.as_asgi()),
    re_path(r'ws/practice/(?P<session_id>\d+)/$', consumers.PracticeSessionConsumer.as_asgi()),
]
