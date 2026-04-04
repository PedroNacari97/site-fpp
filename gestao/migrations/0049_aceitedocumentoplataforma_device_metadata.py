from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0048_documentoplataforma_aceitedocumentoplataforma"),
    ]

    operations = [
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="browser_name",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="browser_version",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="device_language",
            field=models.CharField(blank=True, max_length=40),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="device_timezone",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="device_type",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="geolocation_accuracy_meters",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="geolocation_status",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="latitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="longitude",
            field=models.DecimalField(blank=True, decimal_places=6, max_digits=9, null=True),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="os_name",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="os_version",
            field=models.CharField(blank=True, max_length=60),
        ),
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="screen_resolution",
            field=models.CharField(blank=True, max_length=40),
        ),
    ]
