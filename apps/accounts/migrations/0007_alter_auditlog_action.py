from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0006_guardianrelationship_dependent_approved_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='action',
            field=models.CharField(choices=[
                ('VIEW_PILGRIM', _('Viewed Pilgrim Record')),
                ('SCAN_QR', _('Scanned Lost Pilgrim QR')),
                ('EXPORT_REPORT', _('Exported Operations CSV')),
                ('ASSIGN_TICKET', _('Assigned Field Unit')),
                ('RESOLVE_INCIDENT', _('Resolved SOS Ticket')),
                ('GROUP_CHAT', _('Group chat action')),
                ('GROUP_MANAGEMENT', _('Group management action')),
            ], max_length=50),
        ),
    ]
