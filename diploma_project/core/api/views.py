from django.db import transaction
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from core.api.permissions import (
    IsContributionOwnerRequestOwnerOrStaff,
    IsRequestOwnerOrStaff,
    IsVerifiedAndNotBanned,
)
from core.api.serializers import (
    ContributionOwnerActionSerializer,
    ContributionSerializer,
    RequestSerializer,
)
from core.models import Contribution, Request


class RequestViewSet(viewsets.ModelViewSet):
    queryset = Request.objects.all().order_by("-created_at")
    serializer_class = RequestSerializer

    def get_permissions(self):
        if self.action in ("list", "retrieve"):
            return [AllowAny()]
        if self.action in ("create",):
            return [IsAuthenticated(), IsVerifiedAndNotBanned()]
        if self.action in ("partial_update", "update", "close"):
            return [IsAuthenticated(), IsVerifiedAndNotBanned(), IsRequestOwnerOrStaff()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        # Keep public API consistent with UI: hide hidden requests for anonymous.
        user = getattr(self.request, "user", None)
        if not user or not user.is_authenticated:
            return qs.filter(is_hidden=False).exclude(status=Request.STATUS_CLOSED)
        # For normal users, keep hidden requests invisible unless staff or owner.
        if user.is_staff or user.is_superuser:
            return qs
        return qs.filter(is_hidden=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=["post"])
    def close(self, request, pk=None):
        req: Request = self.get_object()
        reason = (request.data or {}).get("reason", "") or ""
        with transaction.atomic():
            req.closed_at = timezone.now()
            req.closed_reason = reason.strip()
            req.status = Request.STATUS_CLOSED
            req.save(update_fields=["closed_at", "closed_reason", "status"])
        return Response(self.get_serializer(req).data)


class ContributionViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = ContributionSerializer
    permission_classes = [IsAuthenticated, IsVerifiedAndNotBanned]

    def get_queryset(self):
        user = self.request.user
        qs = Contribution.objects.select_related("request", "user").order_by("-created_at")
        if user.is_staff or user.is_superuser:
            return qs
        # Normal user: only own contributions + contributions to own requests.
        return qs.filter(user=user) | qs.filter(request__created_by=user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, status=Contribution.STATUS_PROPOSED)

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[IsAuthenticated, IsVerifiedAndNotBanned, IsContributionOwnerRequestOwnerOrStaff],
    )
    def owner_action(self, request, pk=None):
        """
        Owner action performed by the *request owner* (or staff):
        approve -> pending
        decline -> declined
        request_changes -> revision_requested
        """
        contrib: Contribution = self.get_object()
        req = contrib.request
        user = request.user
        if not (user.is_staff or user.is_superuser) and req.created_by_id != user.id:
            return Response({"detail": "Only request owner can perform this action."}, status=403)

        payload = ContributionOwnerActionSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        action = payload.validated_data["action"]
        note = payload.validated_data.get("note", "") or ""

        with transaction.atomic():
            if action == "approve":
                contrib.status = Contribution.STATUS_PENDING
                contrib.owner_note = note.strip()
                # expires_at is set by Contribution.save() on transition PROPOSED -> PENDING
                contrib.save(update_fields=["status", "owner_note"])
            elif action == "decline":
                contrib.status = Contribution.STATUS_DECLINED
                contrib.owner_note = note.strip()
                contrib.save(update_fields=["status", "owner_note"])
            else:
                contrib.status = Contribution.STATUS_REVISION_REQUESTED
                contrib.owner_note = note.strip()
                contrib.save(update_fields=["status", "owner_note"])

        return Response(self.get_serializer(contrib).data)

