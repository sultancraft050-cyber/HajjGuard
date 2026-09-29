from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('accounts', '0002_pilgrimprofile_consent_given_and_more')]
    operations = [
        migrations.AlterField(
            model_name='pilgrimprofile', name='consent_given',
            field=models.BooleanField(
                default=False,
                help_text='Explicit consent for the selected HajjGuard processing purposes',
            ),
        ),
        migrations.AlterField(
            model_name='pilgrimprofile', name='consent_timestamp',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
