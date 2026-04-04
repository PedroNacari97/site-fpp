from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0042_alertaviagem_expiracao_regras"),
    ]

    operations = [
        migrations.CreateModel(
            name="InteresseViagemCliente",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(blank=True, max_length=120)),
                ("continente", models.CharField(blank=True, max_length=60)),
                ("pais", models.CharField(blank=True, max_length=120)),
                ("cidade_destino", models.CharField(blank=True, max_length=120)),
                ("origem", models.CharField(blank=True, max_length=10)),
                ("destino", models.CharField(blank=True, max_length=10)),
                (
                    "classe",
                    models.CharField(
                        blank=True,
                        choices=[("", "Qualquer classe"), ("economica", "Econômica"), ("executiva", "Executiva")],
                        max_length=20,
                    ),
                ),
                ("programa_fidelidade", models.CharField(blank=True, max_length=120)),
                ("companhia_aerea", models.CharField(blank=True, max_length=120)),
                ("meses_ida", models.JSONField(blank=True, default=list)),
                ("meses_volta", models.JSONField(blank=True, default=list)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
                (
                    "cliente",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="interesses_viagem", to="gestao.cliente"),
                ),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="InteresseViagemMatch",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("motivos", models.JSONField(blank=True, default=list)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                (
                    "alerta",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="matches_interesse", to="gestao.alertaviagem"),
                ),
                (
                    "interesse",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="matches_alerta", to="gestao.interesseviagemcliente"),
                ),
            ],
            options={
                "ordering": ["-criado_em"],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("interesse", "alerta"),
                        name="unique_interesse_alerta_match",
                    )
                ],
            },
        ),
    ]
