from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('groups', '0002_pilgrimtrip_locationsharegrant_groupgeofence_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='groupmessage',
            name='is_announcement',
            field=models.BooleanField(default=False),
        ),
    ]
