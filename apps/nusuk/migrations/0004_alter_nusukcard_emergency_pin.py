from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('nusuk', '0003_nusukcard_barcode_code_nusukcard_emergency_pin_and_more')]
    operations = [
        migrations.AlterField(
            model_name='nusukcard', name='emergency_pin',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
    ]
