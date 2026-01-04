from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("gestao", "0029_emissaopassagem_custo_total_criado_em_valor_taxas"),
    ]

    operations = [
        migrations.CreateModel(
            name="AlertaViagem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=255)),
                ("conteudo", models.TextField()),
                ("continente", models.CharField(max_length=60)),
                ("pais", models.CharField(max_length=120)),
                ("cidade_destino", models.CharField(max_length=120)),
                ("origem", models.CharField(max_length=10)),
                ("destino", models.CharField(max_length=10)),
                ("classe", models.CharField(choices=[("economica", "Econômica"), ("executiva", "Executiva")], max_length=20)),
                ("programa_fidelidade", models.CharField(max_length=120)),
                ("companhia_aerea", models.CharField(max_length=120)),
                ("valor_milhas", models.IntegerField(blank=True, null=True)),
                ("valor_reais", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("datas_ida", models.JSONField(blank=True, default=list)),
                ("datas_volta", models.JSONField(blank=True, default=list)),
                ("ativo", models.BooleanField(default=True)),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
        migrations.CreateModel(
            name="NotificacaoSistema",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("titulo", models.CharField(max_length=255)),
                ("mensagem", models.TextField()),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("lida", models.BooleanField(default=False)),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
    ]
