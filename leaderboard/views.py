from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from users.models import User
from .serializers import LeaderboardUserSerializer


class LeaderboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sort_by = request.query_params.get("sort", "chat_count")
        allowed = ["chat_count", "practice_count", "ielts_count", "cefr_count"]
        if sort_by not in allowed:
            sort_by = "chat_count"
        users = User.objects.all().order_by(f"-{sort_by}")[:50]
        return Response(LeaderboardUserSerializer(users, many=True).data)
