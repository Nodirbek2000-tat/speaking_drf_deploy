from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from .models import User, Referral


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)
    referral_code = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name', 'referral_code']

    def create(self, validated_data):
        ref_code = validated_data.pop('referral_code', None)
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        if ref_code:
            try:
                referrer = User.objects.get(referral_code=ref_code)
                user.referred_by = referrer
                user.save(update_fields=['referred_by'])
                Referral.objects.create(referrer=referrer, referred=user)
                # Check if referrer now has 2 premium referrals
                premium_refs = Referral.objects.filter(referrer=referrer, referred__is_premium=False).count()
                total_refs = Referral.objects.filter(referrer=referrer).count()
                if total_refs % 2 == 0:
                    from django.utils import timezone
                    from datetime import timedelta
                    referrer.is_premium = True
                    referrer.premium_expires = timezone.now() + timedelta(days=30)
                    referrer.save(update_fields=['is_premium', 'premium_expires'])
            except User.DoesNotExist:
                pass
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(**data)
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        tokens = RefreshToken.for_user(user)
        return {
            'access': str(tokens.access_token),
            'refresh': str(tokens),
            'user': UserSerializer(user).data
        }


class UserSerializer(serializers.ModelSerializer):
    has_premium = serializers.SerializerMethodField()
    can_search = serializers.SerializerMethodField()
    referral_link = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'avatar', 'bio', 'native_language', 'target_level',
            'is_premium', 'premium_expires', 'has_premium',
            'referral_code', 'referral_link', 'can_search',
            'chat_count', 'practice_count', 'ielts_count', 'cefr_count',
            'free_searches_used', 'is_online', 'last_seen',
            'avg_rating', 'created_at',
        ]
        read_only_fields = ['referral_code', 'chat_count', 'practice_count', 'is_online']

    def get_has_premium(self, obj):
        return obj.has_premium_active

    def get_can_search(self, obj):
        return obj.can_search_partner

    def get_referral_link(self, obj):
        return f"https://t.me/your_bot?start=ref_{obj.referral_code}"

    def get_avg_rating(self, obj):
        ratings = obj.received_ratings.all()
        if not ratings.exists():
            return None
        return round(sum(r.rating for r in ratings) / ratings.count(), 1)


class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'bio', 'native_language', 'target_level', 'avatar']
