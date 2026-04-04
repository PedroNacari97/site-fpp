from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0046_cotacaovoo_mostrar_valor_parcelado"),
    ]

    operations = [
        migrations.AddField(
            model_name="cotacaovoo",
            name="duracao_voo_ida_minutos",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="cotacaovoo",
            name="duracao_voo_volta_minutos",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="cotacaovoo",
            name="fuso_horario_ida",
            field=models.SmallIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="cotacaovoo",
            name="fuso_horario_volta",
            field=models.SmallIntegerField(default=0),
        ),
    ]
