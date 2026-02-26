from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.RegisterView.as_view()),
    path('login/', views.LoginView.as_view()),
    path('profile/', views.ProfileView.as_view()),
    path('online/', views.SetOnlineView.as_view()),
    path('offline/', views.SetOfflineView.as_view()),
    path('statistics/', views.StatisticsView.as_view()),
    path('bot/activity/', views.BotActivityLogView.as_view()),
    path('bot/statistics/', views.BotStatisticsView.as_view()),
    path('bot/tense-stats/', views.TenseSyncView.as_view()),
    path('tense-stats/', views.UserTenseStatsView.as_view()),
    path('my-analysis/', views.MyAnalysisView.as_view()),
]
