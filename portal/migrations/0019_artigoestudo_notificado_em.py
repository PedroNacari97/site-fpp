from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0018_preuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="artigoestudo",
            name="notificado_em",
            field=models.DateTimeField(
                null=True,
                blank=True,
                db_index=True,
                help_text=(
                    "Quando as notificacoes de artigo novo foram disparadas "
                    "para os inscritos (OptInArtigoNovo). Null = ainda nao enviado."
                ),
            ),
        ),
    ]
