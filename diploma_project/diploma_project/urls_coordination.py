from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.urls import include, path
from django.conf.urls.i18n import i18n_patterns

from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView


urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    # OAuth callback endpoint for demos (shows ?code=... or ?error=...)
    path(
        "oauth/callback",
        lambda request: HttpResponse(
            "<!doctype html><html><head><meta charset='utf-8'><title>OAuth callback</title></head>"
            "<body><h1>OAuth callback</h1>"
            "<pre>"
            + "\n".join(f"{k}={v}" for k, v in request.GET.items())
            + "</pre>"
            "<p>Copy <code>code</code> value for POST /o/token/.</p>"
            "</body></html>",
            content_type="text/html",
        ),
        name="oauth_callback",
    ),
    # REST API (coordination resource server)
    path("api/", include("core.api.urls")),
    path("api/auth/jwt/token/", TokenObtainPairView.as_view(), name="api-jwt-token"),
    path("api/auth/jwt/refresh/", TokenRefreshView.as_view(), name="api-jwt-refresh"),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/swagger/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs-swagger"),
    path("api/docs/redoc/", SpectacularRedocView.as_view(url_name="api-schema"), name="api-docs-redoc"),
]

urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
)

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

