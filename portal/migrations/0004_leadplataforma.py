from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_portalmetricdaily_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="LeadPlataforma",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nome_completo", models.CharField(max_length=180)),
                ("empresa", models.CharField(max_length=180)),
                ("cargo", models.CharField(blank=True, max_length=120)),
                ("email", models.EmailField(max_length=254)),
                ("telefone", models.CharField(max_length=40)),
                (
                    "equipe_tamanho",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("1-2", "1 a 2 pessoas"),
                            ("3-5", "3 a 5 pessoas"),
                            ("6-10", "6 a 10 pessoas"),
                            ("11-20", "11 a 20 pessoas"),
                            ("21+", "Mais de 20 pessoas"),
                        ],
                        max_length=20,
                    ),
                ),
                ("mensagem", models.TextField(blank=True)),
                ("aceite_versao", models.CharField(blank=True, max_length=40)),
                ("aceito_em", models.DateTimeField(blank=True, null=True)),
                ("aceito_ip", models.CharField(blank=True, max_length=45)),
                ("aceito_user_agent", models.CharField(blank=True, max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("novo", "Novo"),
                            ("contatado", "Contatado"),
                            ("qualificado", "Qualificado"),
                            ("arquivado", "Arquivado"),
                        ],
                        default="novo",
                        max_length=20,
                    ),
                ),
                ("criado_em", models.DateTimeField(auto_now_add=True)),
                ("atualizado_em", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-criado_em"],
            },
        ),
    ]
