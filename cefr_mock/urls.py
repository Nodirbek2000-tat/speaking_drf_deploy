from django.urls import path
from . import views

urlpatterns = [
    path("start/", views.StartCEFRSessionView.as_view()),
    path("<int:session_id>/answer/<int:question_id>/", views.SubmitCEFRAnswerView.as_view()),
    path("<int:session_id>/finish/", views.FinishCEFRSessionView.as_view()),
    path("my-sessions/", views.MyCEFRSessionsView.as_view()),
    path("bot/questions/", views.BotCEFRQuestionsView.as_view()),
]
