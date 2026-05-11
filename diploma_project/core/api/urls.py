from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core.api.views import ContributionViewSet, RequestViewSet


router = DefaultRouter()
router.register(r"requests", RequestViewSet, basename="api-requests")
router.register(r"contributions", ContributionViewSet, basename="api-contributions")

urlpatterns = [
    path("", include(router.urls)),
]

