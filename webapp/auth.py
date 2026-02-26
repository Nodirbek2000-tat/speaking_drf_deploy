"""Telegram Web App initData verification"""
import hashlib
import hmac
import json
from urllib.parse import unquote


def verify_telegram_webapp(init_data: str, bot_token: str) -> dict | None:
    """
    Verify Telegram Web App initData.
    Returns user dict if valid, None if invalid.
    """
    try:
        if not init_data or not bot_token:
            return None

        decoded = unquote(init_data)
        parts = dict(item.split('=', 1) for item in decoded.split('&') if '=' in item)

        hash_value = parts.pop('hash', None)
        if not hash_value:
            return None

        data_check_string = '\n'.join(
            f"{k}={v}" for k, v in sorted(parts.items())
        )

        secret_key = hmac.new(
            b'WebAppData',
            bot_token.encode('utf-8'),
            hashlib.sha256
        ).digest()

        computed_hash = hmac.new(
            secret_key,
            data_check_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()

        if computed_hash != hash_value:
            return None

        user_str = parts.get('user', '{}')
        user_data = json.loads(user_str)
        return user_data

    except Exception:
        return None


def get_or_create_webapp_user(user_data: dict):
    """
    Get or create Django user from Telegram user data.
    Returns (user, created) tuple.
    """
    from users.models import User

    telegram_id = user_data.get('id')
    if not telegram_id:
        return None, False

    first_name = user_data.get('first_name', '')
    last_name = user_data.get('last_name', '')
    username = user_data.get('username', '') or f'tg_{telegram_id}'

    # Try to find by telegram_id
    photo_url = user_data.get('photo_url', '')

    try:
        user = User.objects.get(telegram_id=telegram_id)
        # Update fields if changed
        update_fields = []
        if user.first_name != first_name:
            user.first_name = first_name
            update_fields.append('first_name')
        if user.last_name != last_name:
            user.last_name = last_name
            update_fields.append('last_name')
        tg_username = username if username != f'tg_{telegram_id}' else user.username
        if tg_username and user.username != tg_username:
            # Check uniqueness
            if not User.objects.filter(username=tg_username).exclude(pk=user.pk).exists():
                user.username = tg_username
                update_fields.append('username')
        if photo_url and user.telegram_photo_url != photo_url:
            user.telegram_photo_url = photo_url
            update_fields.append('telegram_photo_url')
        if update_fields:
            user.save(update_fields=update_fields)
        return user, False
    except User.DoesNotExist:
        pass

    # Create new user — make unique username
    base_username = username.lower()
    final_username = base_username
    counter = 1
    while User.objects.filter(username=final_username).exists():
        final_username = f"{base_username}_{counter}"
        counter += 1

    user = User.objects.create_user(
        username=final_username,
        first_name=first_name,
        last_name=last_name,
        telegram_id=telegram_id,
        telegram_photo_url=photo_url,
        password=None,
    )
    return user, True
