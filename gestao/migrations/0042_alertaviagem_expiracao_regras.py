from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0041_telegramalertaevento"),
    ]

    operations = [
        migrations.AddField(
            model_name="alertaviagem",
            name="manter_apos_cinco_dias",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="alertaviagem",
            name="ocultar_apos_datas",
            field=models.BooleanField(default=False),
        ),
    ]
