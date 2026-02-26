from django.urls import path
from . import views

urlpatterns = [
    path("categories/", views.PracticeCategoryListView.as_view()),
    path("scenarios/", views.PracticeScenarioListView.as_view()),
    path("start/<int:scenario_id>/", views.StartPracticeSessionView.as_view()),
    path("session/<int:session_id>/send/", views.SendPracticeMessageView.as_view()),
    path("session/<int:session_id>/end/", views.EndPracticeSessionView.as_view()),
    path("my-sessions/", views.MyPracticeSessionsView.as_view()),
]
