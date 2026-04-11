from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0007_alertemaildigestitem"),
    ]

    operations = [
        migrations.AddField(
            model_name="leadalertaemail",
            name="motivo_cancelamento",
            field=models.CharField(
                blank=True,
                choices=[
                    ("muitos_emails", "Recebo muitos e-mails"),
                    ("conteudo_irrelevante", "O conteudo nao e relevante para mim"),
                    ("sem_interesse", "Nao tenho mais interesse nos alertas"),
                    ("nao_reconhece_cadastro", "Nao lembro de ter me cadastrado"),
                    ("caixa_cheia", "Quero reduzir mensagens na caixa de entrada"),
                ],
                max_length=40,
            ),
        ),
        migrations.AddField(
            model_name="leadalertaemail",
            name="cancelado_em",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
