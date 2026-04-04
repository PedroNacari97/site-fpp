from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0044_interesseviagemcliente_janelas_flexiveis"),
    ]

    operations = [
        migrations.AddField(
            model_name="movimentacao",
            name="chave_origem",
            field=models.CharField(blank=True, default="", max_length=120),
        ),
        migrations.AddField(
            model_name="movimentacao",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("manual", "Manual"),
                    ("emissao", "Emissão"),
                    ("transferencia", "Transferência"),
                    ("clube", "Clube"),
                ],
                default="manual",
                max_length=20,
            ),
        ),
    ]
