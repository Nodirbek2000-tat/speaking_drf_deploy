from django.urls import path
from . import views

urlpatterns = [
    path("plans/", views.PremiumPlanListView.as_view()),
    path("buy/", views.BuyPremiumView.as_view()),
    path("my-purchases/", views.MyPurchasesView.as_view()),
]
