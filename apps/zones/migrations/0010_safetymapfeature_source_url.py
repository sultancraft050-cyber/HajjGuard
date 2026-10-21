from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('zones', '0009_haramlocation'),
    ]

    operations = [
        migrations.AddField(
            model_name='safetymapfeature',
            name='source_url',
            field=models.URLField(blank=True, help_text='Public evidence URL; never include private credentials.'),
        ),
    ]
