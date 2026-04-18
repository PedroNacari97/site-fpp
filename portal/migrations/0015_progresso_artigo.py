# Portal B2C — Progresso de leitura por artigo (Tarefa 5)
# Gerada manualmente. Depende de 0014 (PortalUser) e 0012 (ArtigoEstudo).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0014_portaluser_optins_b2c"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProgressoArtigo",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("lido_em", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("primeira_visita_em", models.DateTimeField(auto_now_add=True)),
                ("ultima_visita_em", models.DateTimeField(auto_now=True)),
                ("progresso_percentual", models.PositiveSmallIntegerField(default=0)),
                (
                    "artigo",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progressos",
                        to="portal.artigoestudo",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="progressos_artigo",
                        to="portal.portaluser",
                    ),
                ),
            ],
            options={
                "verbose_name": "Progresso de artigo",
                "verbose_name_plural": "Progressos de artigos",
                "ordering": ["-ultima_visita_em"],
            },
        ),
        migrations.AddConstraint(
            model_name="progressoartigo",
            constraint=models.UniqueConstraint(
                fields=("user", "artigo"),
                name="unique_progresso_user_artigo",
            ),
        ),
        migrations.AddIndex(
            model_name="progressoartigo",
            index=models.Index(
                fields=["user", "artigo"],
                name="portal_prog_user_id_artigo_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="progressoartigo",
            index=models.Index(
                fields=["user", "lido_em"],
                name="portal_prog_user_lido_idx",
            ),
        ),
    ]
