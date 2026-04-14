from django.db import migrations


def add_aeroporto(apps, schema_editor):
    Aeroporto = apps.get_model("gestao", "Aeroporto")
    Aeroporto.objects.get_or_create(
        sigla="VVI",
        defaults={
            "nome": "Aeroporto Internacional Viru Viru",
            "cidade": "Santa Cruz de la Sierra",
            "estado": "Bolivia",
        },
    )


def remove_aeroporto(apps, schema_editor):
    apps.get_model("gestao", "Aeroporto").objects.filter(sigla="VVI").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0062_add_aeroportos_sdu_lim_gig"),
    ]

    operations = [
        migrations.RunPython(add_aeroporto, remove_aeroporto),
    ]
