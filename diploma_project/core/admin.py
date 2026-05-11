from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import (
    AuditLogEntry,
    Contribution,
    Conversation,
    Dispute,
    Message,
    ModerationReport,
    Profile,
    Request,
)


@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'total_quantity', 'remaining_quantity', 'status', 'created_at', 'created_by')
    list_filter = ('category', 'status')
    search_fields = ('title',)


@admin.register(Contribution)
class ContributionAdmin(admin.ModelAdmin):
    list_display = ('user', 'request', 'quantity', 'status', 'expires_at', 'verification_code', 'created_at')
    list_filter = ('status',)
    search_fields = ('verification_code', 'user__username', 'request__title')
    readonly_fields = ('verification_code', 'created_at', 'expires_at')
    actions = ('mark_approved', 'mark_rejected', 'mark_verified')

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj=obj))
        if obj is not None:
            # Prevent changing quantity/request after it's been applied.
            ro.extend(['quantity', 'request', 'user'])
        return ro

    @admin.action(description="Approve selected contributions")
    def mark_approved(self, request, queryset):
        updated = queryset.filter(status='pending').update(status='approved')
        self.message_user(request, f"Approved {updated} contribution(s).", level=messages.SUCCESS)

    @admin.action(description="Reject selected contributions (restores remaining quantity)")
    def mark_rejected(self, request, queryset):
        count = 0
        for c in queryset:
            if c.status in ('rejected', 'expired'):
                continue
            c.status = 'rejected'
            try:
                c.save()
                count += 1
            except ValidationError as e:
                self.message_user(request, f"Could not reject {c.id}: {e}", level=messages.ERROR)
        self.message_user(request, f"Rejected {count} contribution(s).", level=messages.SUCCESS)

    @admin.action(description="Verify selected contributions (requires proof + approved)")
    def mark_verified(self, request, queryset):
        verified = 0
        blocked = 0
        for c in queryset:
            if c.status == 'verified':
                continue
            if c.status != 'approved' or not c.proof_file:
                blocked += 1
                continue
            c.status = 'verified'
            c.save(update_fields=['status'])
            verified += 1
        if verified:
            self.message_user(request, f"Verified {verified} contribution(s).", level=messages.SUCCESS)
        if blocked:
            self.message_user(
                request,
                f"Skipped {blocked} contribution(s): must be approved and have proof uploaded.",
                level=messages.WARNING,
            )

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "is_verified", "verification_status", "restricted_until", "banned_at")
    list_filter = ("role", "verification_status")
    search_fields = ("user__username", "user__email", "phone_number")


@admin.register(ModerationReport)
class ModerationReportAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "score", "created_at", "created_by", "reason")
    list_filter = ("status",)
    search_fields = ("snapshot_title", "snapshot_description", "reason", "created_by__username")
    readonly_fields = ("created_at", "action_at", "action_by")
    fieldsets = (
        (
            "Report",
            {
                "fields": (
                    "status",
                    "created_at",
                    "created_by",
                    "request",
                    "reason",
                    "score",
                    "snapshot_title",
                    "snapshot_description",
                    "snapshot_category",
                )
            },
        ),
        (
            "Resolution",
            {
                "fields": (
                    "resolved_at",
                    "resolved_by",
                    "admin_note",
                )
            },
        ),
        (
            "Enforcement action",
            {
                "fields": (
                    "action_taken",
                    "action_duration_hours",
                    "action_note",
                    "action_at",
                    "action_by",
                )
            },
        ),
    )


@admin.register(Dispute)
class DisputeAdmin(admin.ModelAdmin):
    list_display = ('id', 'contribution', 'created_by', 'status', 'created_at', 'resolved_at')
    list_filter = ('status',)
    search_fields = ('reason', 'admin_note', 'created_by__username', 'contribution__verification_code')
    readonly_fields = ('created_at', 'resolved_at')
    actions = ('mark_resolved',)

    @admin.action(description="Mark selected disputes as resolved")
    def mark_resolved(self, request, queryset):
        updated = queryset.exclude(status='resolved').update(status='resolved', resolved_at=timezone.now())
        self.message_user(request, f"Resolved {updated} dispute(s).", level=messages.SUCCESS)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'resource_request', 'contributor', 'receiver', 'last_activity_at', 'created_at')
    search_fields = ('resource_request__title', 'contributor__username', 'receiver__username')


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'sender', 'created_at')
    search_fields = ('body',)


@admin.register(AuditLogEntry)
class AuditLogEntryAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target_user", "target_request", "target_contribution", "ip")
    list_filter = ("action", "created_at")
    search_fields = (
        "action",
        "actor__username",
        "target_user__username",
        "target_request__title",
        "ip",
    )
    readonly_fields = ("created_at", "actor", "action", "target_user", "target_request", "target_contribution", "ip", "user_agent", "meta")