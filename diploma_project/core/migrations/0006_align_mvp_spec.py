# Generated manually to avoid interactive makemigrations prompts.

import uuid

from django.conf import settings
from django.db import migrations, models


def backfill_request_remaining_and_status(apps, schema_editor):
    Request = apps.get_model("core", "Request")
    for r in Request.objects.all():
        # If the row is coming from older schema, treat total_quantity as source of truth.
        if r.remaining_quantity is None:
            r.remaining_quantity = r.total_quantity
        if r.remaining_quantity == 0:
            r.status = "closed"
        elif r.remaining_quantity < r.total_quantity:
            r.status = "partially_fulfilled"
        else:
            r.status = "open"
        r.save(update_fields=["remaining_quantity", "status"])


def backfill_contribution_verification_code(apps, schema_editor):
    Contribution = apps.get_model("core", "Contribution")
    for c in Contribution.objects.all():
        if c.verification_code is None:
            c.verification_code = uuid.uuid4()
            c.save(update_fields=["verification_code"])


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0005_remove_request_status_request_total_needed_and_more"),
    ]

    operations = [
        # Request: rename fields to match spec
        migrations.RenameField(model_name="request", old_name="type", new_name="category"),
        migrations.RenameField(model_name="request", old_name="total_needed", new_name="total_quantity"),
        migrations.RenameField(model_name="request", old_name="user", new_name="created_by"),
        migrations.AlterField(
            model_name="request",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.SET_NULL,
                related_name="requests_created",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Add remaining/status (nullable first to allow backfill)
        migrations.AddField(
            model_name="request",
            name="remaining_quantity",
            field=models.PositiveIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="request",
            name="status",
            field=models.CharField(
                choices=[
                    ("open", "Open"),
                    ("partially_fulfilled", "Partially fulfilled"),
                    ("closed", "Closed"),
                ],
                default="open",
                max_length=32,
            ),
        ),
        migrations.RunPython(backfill_request_remaining_and_status, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="request",
            name="remaining_quantity",
            field=models.PositiveIntegerField(default=1),
        ),

        # Contribution: rename amount -> quantity
        migrations.RenameField(model_name="contribution", old_name="amount", new_name="quantity"),
        # Remove old tracking_code
        migrations.RemoveField(model_name="contribution", name="tracking_code"),
        # Add verification_code (nullable first, then backfill, then enforce)
        migrations.AddField(
            model_name="contribution",
            name="verification_code",
            field=models.UUIDField(null=True, editable=False),
        ),
        migrations.RunPython(backfill_contribution_verification_code, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="contribution",
            name="verification_code",
            field=models.UUIDField(default=uuid.uuid4, editable=False, unique=True),
        ),

        # Profile: add is_verified, keep role field (choices change doesn't require migration)
        migrations.AddField(
            model_name="profile",
            name="is_verified",
            field=models.BooleanField(default=False),
        ),

        # Remove old Verification model (we store verification in Profile now)
        migrations.DeleteModel(name="Verification"),
    ]

