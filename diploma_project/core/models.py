import uuid
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class Request(models.Model):
    CATEGORY_CHOICES = [
        ('civil', 'Civil'),
        ('military', 'Military'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)

    delivery_location = models.TextField(
        blank=True,
        help_text='Where contributors should send goods (station, building, department, contact window, etc.).',
    )

    COUNTRY_UA = 'UA'
    COUNTRY_OTHER = 'OTHER'
    DELIVERY_COUNTRY_CHOICES = [
        (COUNTRY_UA, 'Ukraine'),
        (COUNTRY_OTHER, 'Other (free text only — no carrier map)'),
    ]
    delivery_country = models.CharField(
        max_length=16,
        choices=DELIVERY_COUNTRY_CHOICES,
        default=COUNTRY_UA,
    )

    DELIVERY_KIND_MANUAL = 'manual'
    DELIVERY_KIND_NOVA = 'nova_poshta'
    DELIVERY_KIND_UKR = 'ukrposhta'
    DELIVERY_KIND_CHOICES = [
        (DELIVERY_KIND_MANUAL, 'Manual description'),
        (DELIVERY_KIND_NOVA, 'Nova Poshta (parcel locker / branch)'),
        (DELIVERY_KIND_UKR, 'Ukrposhta (post office)'),
    ]
    delivery_kind = models.CharField(
        max_length=20,
        choices=DELIVERY_KIND_CHOICES,
        default=DELIVERY_KIND_MANUAL,
    )

    np_city_ref = models.CharField(max_length=64, blank=True)
    np_city_label = models.CharField(max_length=255, blank=True)
    np_warehouse_ref = models.CharField(max_length=64, blank=True)
    np_label = models.TextField(blank=True, help_text='Snapshot of selected NP warehouse for display.')

    up_postcode = models.CharField(max_length=12, blank=True)
    up_office_id = models.CharField(max_length=128, blank=True)
    up_label = models.TextField(blank=True)

    total_quantity = models.PositiveIntegerField(default=1)
    remaining_quantity = models.PositiveIntegerField(default=1)

    STATUS_OPEN = 'open'
    STATUS_PARTIALLY_FULFILLED = 'partially_fulfilled'
    STATUS_CLOSED = 'closed'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_PARTIALLY_FULFILLED, 'Partially fulfilled'),
        (STATUS_CLOSED, 'Closed'),
    ]
    status = models.CharField(max_length=32, choices=STATUS_CHOICES, default=STATUS_OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='requests_created',
        null=True,
        blank=True,
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_reason = models.TextField(blank=True)

    # Staff moderation: hide request from public listings/details
    is_hidden = models.BooleanField(default=False)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests_hidden',
    )
    hidden_reason = models.TextField(blank=True)

    # Staff warning shown publicly on the request.
    staff_warning = models.TextField(blank=True)
    staff_warning_at = models.DateTimeField(null=True, blank=True)
    staff_warning_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='requests_warned',
    )

    def clean(self):
        if self.remaining_quantity > self.total_quantity:
            raise ValidationError({'remaining_quantity': 'Remaining quantity cannot exceed total quantity.'})
        # Civil requests must not contain obvious military content.
        if self.category == 'civil':
            from .content_policy import civil_text_contains_military_terms

            if civil_text_contains_military_terms(self.title, self.description):
                raise ValidationError(
                    {
                        'title': 'You are not available to request military things or your account gonna be restricted.',
                        'description': 'You are not available to request military things or your account gonna be restricted.',
                    }
                )
        if self.delivery_country == self.COUNTRY_OTHER:
            if self.delivery_kind != self.DELIVERY_KIND_MANUAL:
                raise ValidationError({'delivery_kind': 'Only manual delivery text is available outside Ukraine.'})
            if not (self.delivery_location or '').strip():
                raise ValidationError({'delivery_location': 'Describe the handoff location for international requests.'})
        if self.delivery_country == self.COUNTRY_UA:
            if self.delivery_kind == self.DELIVERY_KIND_NOVA:
                if not (self.np_city_ref and self.np_warehouse_ref and self.np_label):
                    raise ValidationError({'np_label': 'Select a Nova Poshta city and warehouse.'})
            if self.delivery_kind == self.DELIVERY_KIND_UKR:
                if not (self.up_postcode and self.up_label):
                    raise ValidationError({'up_label': 'Enter postcode and select an Ukrposhta office.'})

    def _recompute_status(self):
        # Manual closure overrides remaining_quantity-based status.
        if self.status == self.STATUS_CLOSED and self.closed_at:
            return
        if self.remaining_quantity == 0:
            self.status = self.STATUS_CLOSED
        elif self.remaining_quantity < self.total_quantity:
            self.status = self.STATUS_PARTIALLY_FULFILLED
        else:
            self.status = self.STATUS_OPEN

    def save(self, *args, **kwargs):
        if self._state.adding and (self.remaining_quantity is None or self.remaining_quantity == 1):
            # On creation, default remaining to total unless explicitly set.
            # The default value is 1, so detect "not explicitly set" by matching defaults.
            if self.total_quantity:
                self.remaining_quantity = self.total_quantity
        self._recompute_status()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    @property
    def status_badge_class(self) -> str:
        if self.status == self.STATUS_OPEN:
            return "text-bg-success"
        if self.status == self.STATUS_PARTIALLY_FULFILLED:
            return "text-bg-primary"
        if self.status == self.STATUS_CLOSED:
            return "text-bg-secondary"
        return "text-bg-secondary"

    @property
    def fulfilled_quantity(self) -> int:
        return max(0, int(self.total_quantity) - int(self.remaining_quantity))

    @property
    def fulfilled_percent(self) -> int:
        if not self.total_quantity:
            return 0
        return int(round((self.fulfilled_quantity / self.total_quantity) * 100))


class Contribution(models.Model):
    """Fulfillment starts after the request owner accepts a proposal (status → pending)."""

    STATUS_PROPOSED = 'proposed'
    STATUS_REVISION_REQUESTED = 'revision_requested'
    STATUS_DECLINED = 'declined'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_REJECTED = 'rejected'
    STATUS_VERIFIED = 'verified'
    STATUS_EXPIRED = 'expired'
    STATUS_CHOICES = [
        (STATUS_PROPOSED, 'Awaiting request owner'),
        (STATUS_REVISION_REQUESTED, 'Changes requested by owner'),
        (STATUS_DECLINED, 'Declined by request owner'),
        (STATUS_WITHDRAWN, 'Withdrawn by contributor'),
        (STATUS_PENDING, 'Accepted — send within deadline'),
        (STATUS_APPROVED, 'Approved (staff)'),
        (STATUS_REJECTED, 'Rejected (staff)'),
        (STATUS_VERIFIED, 'Verified'),
        (STATUS_EXPIRED, 'Expired (not delivered in time)'),
    ]

    FULFILLMENT_DAYS = 7

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    request = models.ForeignKey(Request, on_delete=models.CASCADE, related_name='contributions')

    quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default=STATUS_PROPOSED)

    contrib_delivery_kind = models.CharField(
        max_length=20,
        choices=Request.DELIVERY_KIND_CHOICES,
        blank=True,
        help_text='Where the contributor will hand off (Ukraine: Nova Poshta or Ukrposhta office).',
    )
    contrib_np_city_ref = models.CharField(max_length=64, blank=True)
    contrib_np_warehouse_ref = models.CharField(max_length=64, blank=True)
    contrib_np_label = models.TextField(blank=True)

    contrib_up_postcode = models.CharField(max_length=12, blank=True)
    contrib_up_office_id = models.CharField(max_length=128, blank=True)
    contrib_up_label = models.TextField(blank=True)

    contrib_dropoff_note = models.TextField(
        blank=True,
        help_text='For non‑UA requests: describe where/how you will ship from.',
    )
    owner_note = models.TextField(blank=True, help_text='Owner feedback when requesting changes or declining.')

    verification_code = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    proof_file = models.FileField(upload_to='proofs/', blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Send goods before this time; otherwise the contribution may expire.',
    )

    def clean(self):
        if self.quantity is None or self.quantity <= 0:
            raise ValidationError({'quantity': 'Quantity must be a positive integer.'})
        if self.status == 'verified' and not self.proof_file:
            raise ValidationError({'proof_file': 'Proof file is required before a contribution can be verified.'})
        req = self.request
        if self.status not in (self.STATUS_PROPOSED, self.STATUS_REVISION_REQUESTED):
            return
        if req.delivery_country == Request.COUNTRY_UA:
            if self.contrib_delivery_kind == Request.DELIVERY_KIND_NOVA:
                if not (self.contrib_np_city_ref and self.contrib_np_warehouse_ref and self.contrib_np_label):
                    raise ValidationError(
                        {'contrib_np_label': 'Select a Nova Poshta city and branch or parcel locker.'}
                    )
            elif self.contrib_delivery_kind == Request.DELIVERY_KIND_UKR:
                if not (self.contrib_up_postcode and self.contrib_up_label):
                    raise ValidationError(
                        {'contrib_up_label': 'Enter postcode and select an Ukrposhta office.'}
                    )
            else:
                raise ValidationError(
                    {'contrib_delivery_kind': 'Choose Nova Poshta or Ukrposhta for your drop-off point.'}
                )
        else:
            if not (self.contrib_dropoff_note or '').strip():
                raise ValidationError({'contrib_dropoff_note': 'Describe how or where you will ship from.'})

    def __str__(self):
        return f"{self.user} -> {self.request.title} ({self.quantity})"

    @property
    def status_badge_class(self) -> str:
        s = self.status
        if s == self.STATUS_PROPOSED:
            return "text-bg-secondary"
        if s == self.STATUS_REVISION_REQUESTED:
            return "text-bg-primary"
        if s in (self.STATUS_DECLINED, self.STATUS_REJECTED):
            return "text-bg-danger"
        if s == self.STATUS_WITHDRAWN:
            return "text-bg-dark"
        if s == self.STATUS_PENDING:
            return "text-bg-warning"
        if s in (self.STATUS_APPROVED, self.STATUS_VERIFIED):
            return "text-bg-success"
        if s == self.STATUS_EXPIRED:
            return "text-bg-secondary"
        return "text-bg-secondary"

    def _reserved_by_others(self, req: Request) -> int:
        qs = Contribution.objects.filter(
            request=req,
            status__in=(self.STATUS_PROPOSED, self.STATUS_REVISION_REQUESTED),
        )
        if self.pk:
            qs = qs.exclude(pk=self.pk)
        return qs.aggregate(s=Sum('quantity'))['s'] or 0

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding

        req = Request.objects.select_for_update().get(pk=self.request_id)

        previous = None
        if not is_new:
            previous = Contribution.objects.select_for_update().get(pk=self.pk)

        if is_new:
            self.status = self.STATUS_PROPOSED
            self.expires_at = None
            reserved_others = self._reserved_by_others(req)
            if self.quantity > req.remaining_quantity - reserved_others:
                raise ValidationError(
                    {
                        'quantity': 'Not enough open capacity (other proposals are already awaiting the owner).'
                    }
                )

        if not is_new and previous:
            if previous.status == self.STATUS_PROPOSED and self.status == self.STATUS_PENDING:
                if self.quantity > req.remaining_quantity:
                    raise ValidationError({'quantity': 'Cannot accept: not enough remaining quantity.'})
                req.remaining_quantity -= self.quantity
                req.save(update_fields=['remaining_quantity', 'status'])
                if not self.expires_at:
                    self.expires_at = timezone.now() + timedelta(days=self.FULFILLMENT_DAYS)

            elif previous.status == self.STATUS_REVISION_REQUESTED and self.status == self.STATUS_PROPOSED:
                reserved_others = self._reserved_by_others(req)
                if self.quantity > req.remaining_quantity - reserved_others:
                    raise ValidationError(
                        {
                            'quantity': 'Not enough open capacity (adjust quantity or wait for other proposals).'
                        }
                    )
                self.owner_note = ''

            elif previous.status in (self.STATUS_PROPOSED, self.STATUS_REVISION_REQUESTED) and self.status == self.STATUS_WITHDRAWN:
                # No reservation yet; just record status.
                self.expires_at = None

            elif (
                previous.status == self.STATUS_PENDING
                and self.status in (self.STATUS_REJECTED, self.STATUS_EXPIRED)
            ):
                req.remaining_quantity = min(req.total_quantity, req.remaining_quantity + previous.quantity)
                req.save(update_fields=['remaining_quantity', 'status'])

        super().save(*args, **kwargs)


class Conversation(models.Model):
    """One thread per (request, contributor) between contributor and request owner."""

    resource_request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    contributor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_contributor',
    )
    receiver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations_as_receiver',
        help_text='Usually the user who created the request.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('resource_request', 'contributor'),
                name='unique_conversation_per_request_contributor',
            ),
        ]
        ordering = ['-last_activity_at']

    def __str__(self):
        return f'Chat {self.resource_request_id}: {self.contributor_id} ↔ {self.receiver_id}'


class Message(models.Model):
    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'Message {self.id}'


class AuditLogEntry(models.Model):
    """Minimal audit log for security-relevant actions."""

    created_at = models.DateTimeField(auto_now_add=True)

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=64)

    target_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events_as_target",
    )
    target_request = models.ForeignKey(
        Request,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    target_contribution = models.ForeignKey(
        Contribution,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )

    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    meta = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self) -> str:
        return f"{self.created_at:%Y-%m-%d %H:%M:%S} {self.action}"


class ModerationReport(models.Model):
    """A lightweight moderation queue entry (AI-assisted / rule-based)."""

    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderation_reports_created',
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)

    # If a request exists (e.g. older content) link it; for blocked submissions we store a snapshot only.
    request = models.ForeignKey(Request, on_delete=models.SET_NULL, null=True, blank=True, related_name='reports')
    snapshot_title = models.CharField(max_length=255, blank=True)
    snapshot_description = models.TextField(blank=True)
    snapshot_category = models.CharField(max_length=20, blank=True)

    reason = models.CharField(max_length=255)
    score = models.PositiveSmallIntegerField(default=0)

    ACTION_NONE = 'none'
    ACTION_UNRESTRICT = 'unrestrict'
    ACTION_RESTRICT_TEMP = 'restrict_temp'
    ACTION_BAN_PERMANENT = 'ban_permanent'
    ACTION_CHOICES = [
        (ACTION_NONE, 'No action'),
        (ACTION_UNRESTRICT, 'Unrestrict'),
        (ACTION_RESTRICT_TEMP, 'Temporary restrict'),
        (ACTION_BAN_PERMANENT, 'Permanent ban'),
    ]
    action_taken = models.CharField(max_length=20, choices=ACTION_CHOICES, default=ACTION_NONE)
    action_note = models.TextField(blank=True)
    action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderation_reports_actioned',
    )
    action_at = models.DateTimeField(null=True, blank=True)
    action_duration_hours = models.PositiveSmallIntegerField(null=True, blank=True)

    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderation_reports_resolved',
    )
    admin_note = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"ModerationReport #{self.id} ({self.status})"


class Profile(models.Model):
    ROLE_CHOICES = [
        ('civil', 'Civil'),
        ('military', 'Military'),
        ('admin', 'Admin'),
    ]

    VERIFICATION_NONE = 'none'
    VERIFICATION_PENDING = 'pending'
    VERIFICATION_VERIFIED = 'verified'
    VERIFICATION_REJECTED = 'rejected'
    VERIFICATION_STATUS_CHOICES = [
        (VERIFICATION_NONE, 'Not submitted'),
        (VERIFICATION_PENDING, 'Pending review'),
        (VERIFICATION_VERIFIED, 'Verified'),
        (VERIFICATION_REJECTED, 'Rejected'),
    ]

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='civil')
    is_verified = models.BooleanField(default=False)

    phone_number = models.CharField(max_length=32, blank=True)
    preferred_dropoff_point = models.TextField(
        blank=True,
        help_text='Your preferred post office / branch / pickup point (free text).',
    )

    preferred_dropoff_kind = models.CharField(
        max_length=20,
        choices=Request.DELIVERY_KIND_CHOICES,
        blank=True,
    )
    preferred_np_city_ref = models.CharField(max_length=64, blank=True)
    preferred_np_warehouse_ref = models.CharField(max_length=64, blank=True)
    preferred_np_city_label = models.CharField(max_length=255, blank=True)
    preferred_np_label = models.TextField(blank=True)

    preferred_up_postcode = models.CharField(max_length=12, blank=True)
    preferred_up_office_id = models.CharField(max_length=128, blank=True)
    preferred_up_label = models.TextField(blank=True)

    passport_scan = models.FileField(upload_to='verifications/', blank=True, null=True)
    reserve_plus_pdf = models.FileField(upload_to='verifications/', blank=True, null=True)
    verification_status = models.CharField(
        max_length=16,
        choices=VERIFICATION_STATUS_CHOICES,
        default=VERIFICATION_NONE,
    )
    verification_note = models.TextField(blank=True)

    # Abuse / policy enforcement (temporary restriction after repeated suspicious attempts).
    restricted_until = models.DateTimeField(null=True, blank=True)
    restricted_reason = models.TextField(blank=True)
    banned_at = models.DateTimeField(null=True, blank=True)
    banned_reason = models.TextField(blank=True)

    profile_photo = models.ImageField(upload_to="profile_photos/", null=True, blank=True)
    profile_photo_public = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


@receiver(post_save, sender=get_user_model())
def create_profile(sender, instance, created, **kwargs):
    if created:
        # Staff/superusers are treated as fully trusted admins (auto-verified).
        if getattr(instance, "is_staff", False) or getattr(instance, "is_superuser", False):
            Profile.objects.create(
                user=instance,
                role="admin",
                is_verified=True,
                verification_status=Profile.VERIFICATION_VERIFIED,
            )
        else:
            Profile.objects.create(user=instance)


@receiver(post_save, sender=get_user_model())
def sync_staff_user_profile(sender, instance, created, **kwargs):
    # Ensure any user toggled to staff/superuser becomes admin+verified.
    if not (getattr(instance, "is_staff", False) or getattr(instance, "is_superuser", False)):
        return
    try:
        p = getattr(instance, "profile", None)
        if not p:
            p = Profile.objects.create(user=instance)
        updates = []
        if p.role != "admin":
            p.role = "admin"
            updates.append("role")
        if not p.is_verified:
            p.is_verified = True
            updates.append("is_verified")
        if p.verification_status != Profile.VERIFICATION_VERIFIED:
            p.verification_status = Profile.VERIFICATION_VERIFIED
            updates.append("verification_status")
        if updates:
            p.save(update_fields=updates)
    except Exception:
        # Best-effort, do not block user saves.
        return


class Dispute(models.Model):
    STATUS_OPEN = 'open'
    STATUS_RESOLVED = 'resolved'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_RESOLVED, 'Resolved'),
    ]

    contribution = models.ForeignKey(Contribution, on_delete=models.CASCADE, related_name='disputes')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='disputes_created')
    reason = models.TextField()
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_OPEN)
    admin_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Dispute #{self.id} ({self.status})"