from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0045_movimentacao_chave_origem_movimentacao_tipo"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotacaovoo",
            name="mostrar_valor_parcelado",
            field=models.BooleanField(default=True),
        ),
    ]
