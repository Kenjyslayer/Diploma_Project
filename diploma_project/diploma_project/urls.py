from django.contrib import admin
from django.urls import path, include

# 👇 додай це
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    # OAuth2 (authorization server)
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
    # REST API (no i18n prefix)
    path("api/", include("core.api.urls")),
    # JWT auth for API
    path("api/auth/jwt/token/", TokenObtainPairView.as_view(), name="api-jwt-token"),
    path("api/auth/jwt/refresh/", TokenRefreshView.as_view(), name="api-jwt-refresh"),
    # OpenAPI schema + docs
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs-swagger"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-docs-redoc"),
]

urlpatterns += i18n_patterns(
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
)

# 👇 і це в самому низу
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)