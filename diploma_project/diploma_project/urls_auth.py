from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import include, path


def oauth2_index(request):
    """GET /o/ — toolkit has no index; show entry points for demos / health checks."""
    body = (
        "<!doctype html><html><head><meta charset='utf-8'><title>OAuth2</title></head><body>"
        "<h1>Auth service (OAuth2)</h1>"
        "<p>django-oauth-toolkit does not serve a page at <code>/o/</code> alone. Use:</p>"
        "<ul>"
        "<li><a href='/o/authorize/'><code>/o/authorize/</code></a> — authorization</li>"
        "<li><code>POST /o/token/</code> — access / refresh token</li>"
        "<li><code>POST /o/revoke_token/</code> — revoke</li>"
        "<li><code>POST /o/introspect/</code> — introspect (if enabled)</li>"
        "</ul>"
        "<p>Register an <strong>Application</strong> in Django admin (coordination UI "
        "<code>/admin/</code> on port 8000) with redirect URI and client credentials.</p>"
        "</body></html>"
    )
    return HttpResponse(body)


urlpatterns = [
    # Root: redirect to OAuth2 index (avoid 404 after login redirect)
    path("", lambda request: redirect("/o/")),
    # Minimal auth UI for OAuth2 authorize flow
    path("login/", auth_views.LoginView.as_view(template_name="core/oauth_login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/o/"), name="logout"),
    path(
        "o/",
        include(
            [
                path("", oauth2_index),
                path("", include("oauth2_provider.urls", namespace="oauth2_provider")),
            ]
        ),
    ),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

