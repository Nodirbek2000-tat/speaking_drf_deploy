from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('webapp/', include('webapp.urls')),
    path('api/auth/', include('users.urls')),
    path('api/chat/', include('chat.urls')),
    path('api/practice/', include('practice.urls')),
    path('api/ielts/', include('ielts_mock.urls')),
    path('api/cefr/', include('cefr_mock.urls')),
    path('api/vocabulary/', include('vocabulary.urls')),
    path('api/premium/', include('premium.urls')),
    path('api/leaderboard/', include('leaderboard.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/token/refresh/', TokenRefreshView.as_view()),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
