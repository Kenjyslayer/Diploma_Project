# Generated manually for contribution proposal / owner approval workflow

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0009_request_delivery_country_request_delivery_kind_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='contribution',
            name='contrib_delivery_kind',
            field=models.CharField(
                blank=True,
                choices=[
                    ('manual', 'Manual description'),
                    ('nova_poshta', 'Nova Poshta (parcel locker / branch)'),
                    ('ukrposhta', 'Ukrposhta (post office)'),
                ],
                help_text='Where the contributor will hand off (Ukraine: Nova Poshta or Ukrposhta office).',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_dropoff_note',
            field=models.TextField(
                blank=True,
                help_text='For non‑UA requests: describe where/how you will ship from.',
            ),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_np_city_ref',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_np_label',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_np_warehouse_ref',
            field=models.CharField(blank=True, max_length=64),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_up_label',
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_up_office_id',
            field=models.CharField(blank=True, max_length=128),
        ),
        migrations.AddField(
            model_name='contribution',
            name='contrib_up_postcode',
            field=models.CharField(blank=True, max_length=12),
        ),
        migrations.AddField(
            model_name='contribution',
            name='owner_note',
            field=models.TextField(
                blank=True, help_text='Owner feedback when requesting changes or declining.'
            ),
        ),
        migrations.AlterField(
            model_name='contribution',
            name='status',
            field=models.CharField(
                choices=[
                    ('proposed', 'Awaiting request owner'),
                    ('revision_requested', 'Changes requested by owner'),
                    ('declined', 'Declined by request owner'),
                    ('pending', 'Accepted — send within deadline'),
                    ('approved', 'Approved (staff)'),
                    ('rejected', 'Rejected (staff)'),
                    ('verified', 'Verified'),
                    ('expired', 'Expired (not delivered in time)'),
                ],
                default='proposed',
                max_length=24,
            ),
        ),
    ]
