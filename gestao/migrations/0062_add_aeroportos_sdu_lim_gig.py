from django.db import migrations


def add_aeroportos(apps, schema_editor):
    Aeroporto = apps.get_model("gestao", "Aeroporto")
    aeroportos = [
        {"sigla": "SDU", "nome": "Aeroporto Santos Dumont", "cidade": "Rio de Janeiro", "estado": "RJ"},
        {"sigla": "LIM", "nome": "Aeroporto Internacional Jorge Chávez", "cidade": "Lima", "estado": "Peru"},
        {"sigla": "GIG", "nome": "Aeroporto Internacional do Galeão", "cidade": "Rio de Janeiro", "estado": "RJ"},
    ]
    for data in aeroportos:
        Aeroporto.objects.get_or_create(sigla=data["sigla"], defaults=data)


def remove_aeroportos(apps, schema_editor):
    Aeroporto = apps.get_model("gestao", "Aeroporto")
    Aeroporto.objects.filter(sigla__in=["SDU", "LIM", "GIG"]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0061_instagramnoticiaevento"),
    ]

    operations = [
        migrations.RunPython(add_aeroportos, remove_aeroportos),
    ]
