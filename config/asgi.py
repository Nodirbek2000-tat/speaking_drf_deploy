import os
import django
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from chat.routing import websocket_urlpatterns as chat_ws
from webapp.routing import websocket_urlpatterns as webapp_ws
from webapp.ws_auth import TokenAuthMiddleware

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    # AuthMiddlewareStack olib tashlandi — TokenAuthMiddleware o'zi hal qiladi
    "websocket": TokenAuthMiddleware(
        URLRouter(chat_ws + webapp_ws)
    ),
})