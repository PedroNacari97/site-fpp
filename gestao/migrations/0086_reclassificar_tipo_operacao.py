from django.db import migrations


def reclassificar_emissoes(apps, schema_editor):
    EmissaoPassagem = apps.get_model("gestao", "EmissaoPassagem")
    EmissaoPassagem.objects.filter(emissor_parceiro__isnull=False).update(
        tipo_operacao="emissor_parceiro"
    )
    EmissaoPassagem.objects.filter(
        emissor_parceiro__isnull=True, tipo_operacao=""
    ).update(tipo_operacao="venda_direta")


def reverter(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0085_cliente_cnpj_cliente_programas_concierge_and_more"),
    ]

    operations = [
        migrations.RunPython(reclassificar_emissoes, reverter),
    ]
