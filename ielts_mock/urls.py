from django.urls import path
from . import views

urlpatterns = [
    path("start/", views.StartIELTSSessionView.as_view()),
    path("<int:session_id>/answer/<int:question_id>/", views.SubmitIELTSAnswerView.as_view()),
    path("<int:session_id>/finish/", views.FinishIELTSSessionView.as_view()),
    path("my-sessions/", views.MyIELTSSessionsView.as_view()),
    path("bot/questions/", views.BotIELTSQuestionsView.as_view()),
]
