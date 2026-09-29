from django.db import migrations
import secrets


def rotate_payloads(apps, schema_editor):
    PilgrimProfile = apps.get_model('accounts', 'PilgrimProfile')
    for profile in PilgrimProfile.objects.all().iterator():
        profile.qr_code_payload = f"HG-{secrets.token_urlsafe(32)}"
        profile.save(update_fields=['qr_code_payload'])


class Migration(migrations.Migration):
    dependencies = [('accounts', '0003_explicit_consent')]
    operations = [migrations.RunPython(rotate_payloads, migrations.RunPython.noop)]
