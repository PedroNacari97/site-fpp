from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0043_interesseviagemcliente_interesseviagemmatch"),
    ]

    operations = [
        migrations.AddField(
            model_name="interesseviagemcliente",
            name="dias_ida",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="interesseviagemcliente",
            name="dias_volta",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="interesseviagemcliente",
            name="semestres_ida",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name="interesseviagemcliente",
            name="semestres_volta",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
