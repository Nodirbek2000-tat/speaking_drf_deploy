from channels.middleware import BaseMiddleware
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser


class TokenAuthMiddleware(BaseMiddleware):
    """
    1) URL da ?token=xxx bo'lsa → cache dan user topadi
    2) Bo'lmasa → Django session orqali user topadi
    AuthMiddlewareStack kerak emas, ikkalasini o'zi hal qiladi.
    """

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params = {}
        for part in query_string.split('&'):
            if '=' in part:
                k, v = part.split('=', 1)
                params[k] = v

        token = params.get('token')

        if token:
            scope['user'] = await get_user_from_token(token)
        else:
            scope['user'] = await get_user_from_session(scope)

        return await self.inner(scope, receive, send)


@database_sync_to_async
def get_user_from_token(token):
    if not token:
        return AnonymousUser()
    from django.core.cache import cache
    from users.models import User
    user_id = cache.get(f"ws_token_{token}")
    if not user_id:
        return AnonymousUser()
    try:
        cache.delete(f"ws_token_{token}")
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return AnonymousUser()


@database_sync_to_async
def get_user_from_session(scope):
    """Django session orqali user topish"""
    try:
        from django.contrib.sessions.backends.db import SessionStore
        headers = dict(scope.get('headers', []))
        cookie_header = headers.get(b'cookie', b'').decode()

        session_id = None
        for part in cookie_header.split(';'):
            part = part.strip()
            if part.startswith('sessionid='):
                session_id = part.split('=', 1)[1]
                break

        if not session_id:
            return AnonymousUser()

        session = SessionStore(session_key=session_id)
        user_id = session.get('_auth_user_id')
        if not user_id:
            return AnonymousUser()

        from users.models import User
        return User.objects.get(id=user_id)
    except Exception:
        return AnonymousUser()

# from channels.middleware import BaseMiddleware
# from channels.db import database_sync_to_async
# from django.contrib.auth.models import AnonymousUser
#
#
# class TokenAuthMiddleware(BaseMiddleware):
#     async def __call__(self, scope, receive, send):
#         scope['user'] = await get_user_from_session(scope)
#         return await self.inner(scope, receive, send)
#
#
# @database_sync_to_async
# def get_user_from_session(scope):
#     try:
#         from django.contrib.sessions.backends.db import SessionStore
#         from users.models import User
#
#         headers = dict(scope.get('headers', []))
#         cookie_header = headers.get(b'cookie', b'').decode('utf-8', errors='ignore')
#
#         session_id = None
#         for part in cookie_header.split(';'):
#             part = part.strip()
#             if part.startswith('sessionid='):
#                 session_id = part.split('=', 1)[1].strip()
#                 break
#
#         if not session_id:
#             return AnonymousUser()
#
#         session = SessionStore(session_key=session_id)
#         user_id = session.get('_auth_user_id')
#
#         if not user_id:
#             return AnonymousUser()
#
#         return User.objects.get(pk=user_id)
#
#     except Exception as e:
#         print(f"WS Auth error: {e}")
#         return AnonymousUser()