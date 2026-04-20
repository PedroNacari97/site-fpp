from django.db import migrations, models


def preencher_codigos_padrao(apps, schema_editor):
    Companhia = apps.get_model("gestao", "CompanhiaAerea")
    mapping = {
        "latam": "LATAM",
        "gol": "GOL",
        "azul": "AZUL",
    }
    for cia in Companhia.objects.all():
        nome = (cia.nome or "").strip().lower()
        for chave, codigo in mapping.items():
            if chave in nome:
                if cia.codigo != codigo:
                    cia.codigo = codigo
                    cia.save(update_fields=["codigo"])
                break


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0087_emissorparceiro_email_emissorparceiro_endereco_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="companhiaaerea",
            name="codigo",
            field=models.CharField(
                blank=True,
                choices=[("LATAM", "LATAM"), ("GOL", "GOL"), ("AZUL", "Azul")],
                help_text="Identificador usado para selecionar o scraper de monitoramento.",
                max_length=10,
                verbose_name="Código do scraper",
            ),
        ),
        migrations.RunPython(preencher_codigos_padrao, reverse_code=migrations.RunPython.noop),
    ]
