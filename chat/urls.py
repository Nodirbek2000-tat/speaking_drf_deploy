from django.urls import path
from . import views

urlpatterns = [
    path('rooms/', views.MyChatRoomsView.as_view()),
    path('rooms/<int:pk>/', views.ChatRoomDetailView.as_view()),
    path('rooms/<int:room_id>/end/', views.EndChatView.as_view()),
    path('rate/', views.RateChatView.as_view()),
    path('online-users/', views.OnlineUsersView.as_view()),
    path('ai/start/', views.StartAIChatView.as_view()),
    path('ai/<int:chat_id>/send/', views.SendAIMessageView.as_view()),
    path('ai/history/', views.MyAIChatsView.as_view()),
]
