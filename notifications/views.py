from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from .models import DailyReport
from .serializers import DailyReportSerializer


class DailyReportListView(generics.ListAPIView):
    serializer_class = DailyReportSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return DailyReport.objects.filter(user=self.request.user)
