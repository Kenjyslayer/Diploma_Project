# Remove optional map pin from requests (drop-off will be handled via profile / policy later)

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0010_contribution_owner_approval'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='request',
            name='dropoff_lat',
        ),
        migrations.RemoveField(
            model_name='request',
            name='dropoff_lng',
        ),
    ]
