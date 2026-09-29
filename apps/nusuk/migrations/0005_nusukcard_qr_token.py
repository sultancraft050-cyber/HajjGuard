from django.db import migrations, models
import secrets
import json


def populate_qr_tokens(apps, schema_editor):
    NusukCard = apps.get_model('nusuk', 'NusukCard')
    for card in NusukCard.objects.filter(qr_token__isnull=True).iterator():
        card.qr_token = secrets.token_urlsafe(32)
        card.qr_payload = json.dumps({'type': 'NUSUK_SMART_CARD', 'version': '2.0-2026', 'token': card.qr_token})
        card.save(update_fields=['qr_token', 'qr_payload'])


class Migration(migrations.Migration):
    dependencies = [('nusuk', '0004_alter_nusukcard_emergency_pin')]

    operations = [
        migrations.AddField(
            model_name='nusukcard', name='qr_token',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=64, null=True, unique=True),
        ),
        migrations.RunPython(populate_qr_tokens, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='nusukcard', name='qr_token',
            field=models.CharField(blank=True, db_index=True, editable=False, max_length=64, unique=True),
        ),
    ]
