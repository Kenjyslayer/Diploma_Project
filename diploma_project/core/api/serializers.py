from django.contrib.auth import get_user_model
from rest_framework import serializers

from core.models import Contribution, Request


User = get_user_model()


class RequestSerializer(serializers.ModelSerializer):
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)
    fulfilled_quantity = serializers.IntegerField(read_only=True)
    fulfilled_percent = serializers.IntegerField(read_only=True)

    class Meta:
        model = Request
        fields = [
            "id",
            "title",
            "description",
            "category",
            "delivery_country",
            "delivery_kind",
            "np_city_ref",
            "np_city_label",
            "np_warehouse_ref",
            "np_label",
            "up_postcode",
            "up_office_id",
            "up_label",
            "delivery_location",
            "total_quantity",
            "remaining_quantity",
            "status",
            "created_at",
            "created_by",
            "created_by_username",
            "closed_at",
            "closed_reason",
            "is_hidden",
            "staff_warning",
            "fulfilled_quantity",
            "fulfilled_percent",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "created_by",
            "created_by_username",
            "status",
            "remaining_quantity",
            "closed_at",
            "is_hidden",
            "staff_warning",
            "fulfilled_quantity",
            "fulfilled_percent",
        ]


class ContributionSerializer(serializers.ModelSerializer):
    request_title = serializers.CharField(source="request.title", read_only=True)
    user_username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Contribution
        fields = [
            "id",
            "request",
            "request_title",
            "user",
            "user_username",
            "quantity",
            "status",
            "owner_note",
            "created_at",
            "expires_at",
            # contributor drop-off
            "contrib_delivery_kind",
            "contrib_np_city_ref",
            "contrib_np_warehouse_ref",
            "contrib_np_label",
            "contrib_up_postcode",
            "contrib_up_office_id",
            "contrib_up_label",
            "contrib_dropoff_note",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_username",
            "created_at",
            "expires_at",
            "status",
        ]


class ContributionOwnerActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "decline", "request_changes"])
    note = serializers.CharField(required=False, allow_blank=True)

