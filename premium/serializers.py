from rest_framework import serializers
from .models import PremiumPlan, PremiumPurchase


class PremiumPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = PremiumPlan
        fields = ["id", "name", "price_usd", "duration_days", "description", "features"]


class PremiumPurchaseSerializer(serializers.ModelSerializer):
    plan = PremiumPlanSerializer(read_only=True)
    plan_id = serializers.PrimaryKeyRelatedField(
        queryset=PremiumPlan.objects.filter(is_active=True), write_only=True, source="plan"
    )

    class Meta:
        model = PremiumPurchase
        fields = ["id", "plan", "plan_id", "status", "telegram_username", "note", "created_at"]
        read_only_fields = ["status", "created_at"]
