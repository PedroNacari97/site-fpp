from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0092_status_programado_e_codigo_reserva_portal"),
    ]

    operations = [
        migrations.AddField(
            model_name="aceitedocumentoplataforma",
            name="url_origem",
            field=models.CharField(
                blank=True,
                default="",
                max_length=500,
                help_text=(
                    "URL absoluta onde o aceite foi registrado (evidencia forense LGPD)"
                ),
            ),
        ),
    ]
