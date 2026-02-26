from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .models import PremiumPlan, PremiumPurchase
from .serializers import PremiumPlanSerializer, PremiumPurchaseSerializer


class PremiumPlanListView(generics.ListAPIView):
    serializer_class = PremiumPlanSerializer
    permission_classes = [IsAuthenticated]
    queryset = PremiumPlan.objects.filter(is_active=True)


class BuyPremiumView(generics.CreateAPIView):
    serializer_class = PremiumPurchaseSerializer
    permission_classes = [IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, telegram_username=self.request.user.username)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        from django.conf import settings
        payment_info = {
            "message": f"To'lov ma'lumotlari {settings.TELEGRAM_PAYMENT_CHAT} ga yuboring",
            "telegram": settings.TELEGRAM_PAYMENT_CHAT,
            "purchase_id": resp.data["id"],
        }
        resp.data["payment_info"] = payment_info
        return resp


class MyPurchasesView(generics.ListAPIView):
    serializer_class = PremiumPurchaseSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return PremiumPurchase.objects.filter(user=self.request.user)
