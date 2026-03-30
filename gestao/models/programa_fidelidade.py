from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models


MAX_PROGRAM_LOGO_SIZE = 50 * 1024


def validate_program_logo(file_obj):
    if not file_obj:
        return

    if getattr(file_obj, "size", 0) > MAX_PROGRAM_LOGO_SIZE:
        raise ValidationError("Envie uma logo com no maximo 50KB.")

    content_type = getattr(file_obj, "content_type", "")
    if content_type and content_type != "image/png":
        raise ValidationError("Envie a logo em PNG com fundo transparente.")


class ProgramaFidelidade(models.Model):
    TIPO_PRINCIPAL = "principal"
    TIPO_VINCULADO = "vinculado"
    TIPOS = (
        (TIPO_PRINCIPAL, "Programa principal"),
        (TIPO_VINCULADO, "Programa vinculado"),
    )
    REGRA_RESET_DIAS = "dias"
    REGRA_RESET_ANO = "ano"
    REGRAS_RESET = (
        (REGRA_RESET_DIAS, "Dias"),
        (REGRA_RESET_ANO, "Ano civil"),
    )

    nome = models.CharField(max_length=100)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(
        max_length=20, choices=TIPOS, default=TIPO_PRINCIPAL
    )
    programa_base = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="programas_vinculados",
    )
    preco_medio_milheiro = models.DecimalField(
        max_digits=10, decimal_places=2, default=0
    )
    quantidade_cpfs_disponiveis = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Quantidade total de CPFs disponiveis no programa",
    )
    limite_cpfs = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Limite configuravel de CPFs por conta fidelidade para este programa.",
    )
    tipo_regra_reset = models.CharField(
        max_length=10,
        choices=REGRAS_RESET,
        default=REGRA_RESET_ANO,
        help_text="Define quando um CPF volta a ficar disponivel para reutilizacao.",
    )
    dias_reset = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Obrigatorio quando a regra de reset for baseada em dias.",
    )
    logo = models.FileField(
        upload_to="programas/logos/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["png"]),
            validate_program_logo,
        ],
        help_text="PNG quadrado, preferencialmente 200x200 ou 400x400, com ate 50KB.",
    )

    def clean(self):
        errors = {}

        if self.tipo == self.TIPO_PRINCIPAL and self.programa_base_id:
            errors["programa_base"] = "Programas principais nao podem ter programa base vinculado."

        if self.tipo == self.TIPO_VINCULADO:
            if not self.programa_base_id:
                errors["programa_base"] = "Selecione um programa base para programas vinculados."
            elif self.programa_base_id == self.id:
                errors["programa_base"] = "Um programa nao pode estar vinculado a ele mesmo."
            elif getattr(self.programa_base, "tipo", self.TIPO_PRINCIPAL) != self.TIPO_PRINCIPAL:
                errors["programa_base"] = "O programa base precisa ser um programa principal."

        if self.tipo_regra_reset == self.REGRA_RESET_DIAS and not self.dias_reset:
            errors["dias_reset"] = "Informe a quantidade de dias para resetar o CPF."
        if self.tipo_regra_reset == self.REGRA_RESET_ANO:
            self.dias_reset = None

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @property
    def is_vinculado(self):
        return self.tipo == self.TIPO_VINCULADO

    @property
    def logo_url(self):
        if not self.logo:
            return ""
        try:
            return self.logo.url
        except ValueError:
            return ""

    @property
    def logo_badge_text(self):
        parts = [chunk[0] for chunk in self.nome.split()[:2] if chunk]
        return ("".join(parts) or "PF").upper()

    def __str__(self):
        return self.nome
