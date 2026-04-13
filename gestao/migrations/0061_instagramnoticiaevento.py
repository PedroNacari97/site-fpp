import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0060_add_performance_indexes"),
        ("portal", "0008_leadalertaemail_cancelamento"),
    ]

    operations = [
        migrations.CreateModel(
            name="InstagramNoticiaEvento",
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
                (
                    "noticia",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="instagram_eventos",
                        to="portal.noticiaPublicada",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pendente", "Pendente"),
                            ("publicado", "Publicado"),
                            ("erro", "Erro"),
                            ("ignorado", "Ignorado"),
                        ],
                        db_index=True,
                        default="pendente",
                        max_length=24,
                    ),
                ),
                ("ig_media_id", models.CharField(blank=True, max_length=64)),
                ("ig_post_id", models.CharField(blank=True, max_length=64)),
                ("caption", models.TextField(blank=True)),
                ("image_url", models.URLField(blank=True, max_length=500)),
                ("tentativas", models.PositiveSmallIntegerField(default=0)),
                ("erro", models.TextField(blank=True)),
                ("payload_json", models.JSONField(blank=True, default=dict)),
                (
                    "criado_em",
                    models.DateTimeField(auto_now_add=True, db_index=True),
                ),
                ("publicado_em", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Evento de notícia Instagram",
                "verbose_name_plural": "Eventos de notícias Instagram",
                "ordering": ["-criado_em"],
            },
        ),
    ]
