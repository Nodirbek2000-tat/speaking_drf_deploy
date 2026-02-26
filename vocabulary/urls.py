from django.urls import path
from . import views

urlpatterns = [
    path("", views.WordListView.as_view()),
    path("lookup/", views.LookupWordView.as_view()),
    path("<int:word_id>/save/", views.SaveWordView.as_view()),
    path("saved/", views.SavedWordsView.as_view()),
    path("practice/", views.PracticeWordView.as_view()),
    path("bot/words/", views.BotVocabularyView.as_view()),
]
