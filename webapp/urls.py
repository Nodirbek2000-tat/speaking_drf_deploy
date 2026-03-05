from django.urls import path
from . import views

app_name = 'webapp'

urlpatterns = [
    # Auth
    path('', views.index, name='index'),
    path('auth/', views.auth_view, name='auth'),
    path('logout/', views.logout_view, name='logout'),
    path('setup/', views.setup, name='setup'),

    path('another/',views.another_view,name='another_type'),

    # Main pages
    path('home/', views.home, name='home'),
    path('speaking/', views.speaking, name='speaking'),
    path('practice/', views.practice, name='practice'),
    path('leaderboard/', views.leaderboard, name='leaderboard'),
    path('premium/', views.premium, name='premium'),

    # Practice session
    path('practice/start/<int:scenario_id>/', views.practice_start, name='practice_start'),
    path('practice/session/<int:session_id>/', views.practice_session, name='practice_session'),
    path('practice/scenario/<int:scenario_id>/detail/', views.scenario_detail, name='scenario_detail'),

    # Speaking API
    path('speaking/rate/<int:room_id>/', views.rate_call, name='rate_call'),
    path('speaking/history/', views.speaking_history, name='speaking_history'),

    # Premium API
    path('premium/buy/<int:plan_id>/', views.buy_premium, name='buy_premium'),

    # Progress
    path('progress/', views.progress, name='progress'),
    path('progress/problems/', views.my_problems_ai, name='my_problems_ai'),

    # Bot Admin API (protected by BOT_SECRET header)
    path('bot-api/channels/', views.bot_api_channels, name='bot_api_channels'),
    path('bot-api/stats/', views.bot_api_stats, name='bot_api_stats'),
    path('bot-api/cancel-premium/', views.bot_api_cancel_premium, name='bot_api_cancel_premium'),
    path('bot-api/grant-premium/', views.bot_api_grant_premium, name='bot_api_grant_premium'),
    path('bot-api/settings/', views.bot_api_settings, name='bot_api_settings'),
    path('bot-api/payment-card/', views.bot_api_payment_card, name='bot_api_payment_card'),
    path('bot-api/premium-request/', views.bot_api_premium_request, name='bot_api_premium_request'),
    path('ws-token/', views.ws_token, name='ws_token'),

    # Bot extended API
    path('bot-api/leaderboard/', views.bot_api_leaderboard, name='bot_api_leaderboard'),
    path('bot-api/save-ielts/', views.bot_api_save_ielts, name='bot_api_save_ielts'),
    path('bot-api/save-cefr/', views.bot_api_save_cefr, name='bot_api_save_cefr'),
    path('bot-api/save-phone/', views.bot_api_save_phone, name='bot_api_save_phone'),
    path('bot-api/check-limit/', views.bot_api_check_limit, name='bot_api_check_limit'),

    # Vocabulary chat
    path('api/vocab-chat/', views.vocab_chat, name='vocab_chat'),
]
