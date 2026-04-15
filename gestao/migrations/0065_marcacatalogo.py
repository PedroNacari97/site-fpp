from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0064_emissaopassagem_duracao_voo_ida_minutos_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="MarcaCatalogo",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome", models.CharField(max_length=120, unique=True)),
                ("nicho", models.CharField(blank=True, db_index=True, max_length=80)),
                ("dominio", models.CharField(blank=True, max_length=120)),
                ("cor_hex", models.CharField(default="#000000", max_length=9)),
                ("logo_url", models.URLField(blank=True, max_length=600)),
                (
                    "keywords",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text=(
                            "Lista de termos (lowercase) usados para detectar a marca no texto. "
                            "Se vazio, o pipeline gera a partir do nome/dominio."
                        ),
                    ),
                ),
                ("ativo", models.BooleanField(db_index=True, default=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Marca (catalogo)",
                "verbose_name_plural": "Marcas (catalogo)",
                "ordering": ["nicho", "nome"],
            },
        ),
    ]
