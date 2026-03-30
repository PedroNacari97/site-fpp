from django.db import migrations, models
import django.core.validators
import gestao.models.programa_fidelidade


class Migration(migrations.Migration):
    dependencies = [
        ("gestao", "0036_emissorparceiro_telefone"),
    ]

    operations = [
        migrations.AddField(
            model_name="programafidelidade",
            name="logo",
            field=models.FileField(
                blank=True,
                help_text="PNG quadrado, preferencialmente 200x200 ou 400x400, com ate 50KB.",
                null=True,
                upload_to="programas/logos/",
                validators=[
                    django.core.validators.FileExtensionValidator(allowed_extensions=["png"]),
                    gestao.models.programa_fidelidade.validate_program_logo,
                ],
            ),
        ),
    ]
