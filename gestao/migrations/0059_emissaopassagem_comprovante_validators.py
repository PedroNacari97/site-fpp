import django.core.validators
from django.db import migrations, models
import gestao.models.emissao_passagem


class Migration(migrations.Migration):

    dependencies = [
        ("gestao", "0058_telegramnoticiaevento"),
    ]

    operations = [
        migrations.AlterField(
            model_name="emissaopassagem",
            name="comprovante_pagamento",
            field=models.FileField(
                blank=True,
                null=True,
                upload_to="emissoes/comprovantes/",
                verbose_name="Comprovante de pagamento",
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["pdf", "jpg", "jpeg", "png"]
                    ),
                    gestao.models.emissao_passagem.validate_comprovante,
                ],
            ),
        ),
    ]
