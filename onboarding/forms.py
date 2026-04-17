from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from gestao.utils import validate_cpf_digits, hash_cpf
from gestao.models import Cliente, Empresa

User = get_user_model()

FIELD_CLASS = "onboarding-field__input"


class OnboardingStep1Form(forms.Form):
    """Etapa 1 — Dados do responsavel."""
    first_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Nome", "class": FIELD_CLASS, "autofocus": True}),
    )
    last_name = forms.CharField(
        max_length=80,
        widget=forms.TextInput(attrs={"placeholder": "Sobrenome", "class": FIELD_CLASS}),
    )
    cpf = forms.CharField(
        max_length=14,
        widget=forms.TextInput(attrs={
            "placeholder": "000.000.000-00",
            "inputmode": "numeric",
            "maxlength": "14",
            "data-mask": "cpf",
            "class": FIELD_CLASS,
        }),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"placeholder": "email@empresa.com", "class": FIELD_CLASS}),
    )
    telefone = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            "placeholder": "(00) 00000-0000",
            "inputmode": "tel",
            "data-mask": "telefone",
            "class": FIELD_CLASS,
        }),
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(attrs={"placeholder": "Minimo 8 caracteres", "class": FIELD_CLASS}),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Confirme a senha", "class": FIELD_CLASS}),
    )

    def clean_cpf(self):
        return validate_cpf_digits(self.cleaned_data["cpf"])

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("Este email ja possui uma conta cadastrada.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") and cleaned.get("confirm_password"):
            if cleaned["password"] != cleaned["confirm_password"]:
                self.add_error("confirm_password", "As senhas nao coincidem.")
        return cleaned


class OnboardingStep2Form(forms.Form):
    """Etapa 2 — Dados da empresa/profissional."""
    tipo_pessoa = forms.ChoiceField(
        choices=[("PJ", "Pessoa Juridica (CNPJ)"), ("PF", "Pessoa Fisica (CPF)")],
        initial="PJ",
        widget=forms.RadioSelect(attrs={"class": "onboarding-field__radio"}),
    )
    nome_fantasia = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Nome fantasia ou nome profissional", "class": FIELD_CLASS}),
    )
    cnpj = forms.CharField(
        max_length=18,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "00.000.000/0000-00",
            "inputmode": "numeric",
            "maxlength": "18",
            "data-mask": "cnpj",
            "class": FIELD_CLASS,
            "id": "id_cnpj",
        }),
    )
    razao_social = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Razao social", "class": FIELD_CLASS}),
    )
    cep = forms.CharField(
        max_length=9,
        required=False,
        widget=forms.TextInput(attrs={
            "placeholder": "00000-000",
            "inputmode": "numeric",
            "maxlength": "9",
            "data-mask": "cep",
            "class": FIELD_CLASS,
            "id": "id_cep",
        }),
    )
    endereco = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Rua, avenida...", "class": FIELD_CLASS, "id": "id_endereco"}),
    )
    numero = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Numero", "class": FIELD_CLASS}),
    )
    complemento = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Sala, andar... (opcional)", "class": FIELD_CLASS}),
    )
    bairro = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Bairro", "class": FIELD_CLASS, "id": "id_bairro"}),
    )
    cidade = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Cidade", "class": FIELD_CLASS, "id": "id_cidade"}),
    )
    estado = forms.CharField(
        max_length=2,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "UF", "maxlength": "2", "class": FIELD_CLASS, "id": "id_estado"}),
    )
    website = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={"placeholder": "https://", "class": FIELD_CLASS}),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("tipo_pessoa") == "PJ":
            if not cleaned.get("cnpj"):
                self.add_error("cnpj", "CNPJ e obrigatorio para pessoa juridica.")
            if not cleaned.get("razao_social"):
                self.add_error("razao_social", "Razao social e obrigatoria para pessoa juridica.")
        return cleaned


class OnboardingStep3Form(forms.Form):
    """Etapa 3 — Aceite do contrato."""
    aceite_termos = forms.BooleanField(
        required=True,
        error_messages={"required": "Voce precisa aceitar os termos para continuar."},
        widget=forms.CheckboxInput(attrs={"class": "onboarding-field__checkbox"}),
    )
    aceite_privacidade = forms.BooleanField(
        required=True,
        error_messages={"required": "Voce precisa aceitar a politica de privacidade."},
        widget=forms.CheckboxInput(attrs={"class": "onboarding-field__checkbox"}),
    )
    aceite_dpa = forms.BooleanField(
        required=True,
        error_messages={"required": "Voce precisa aceitar o DPA."},
        widget=forms.CheckboxInput(attrs={"class": "onboarding-field__checkbox"}),
    )


class OnboardingStep4Form(forms.Form):
    """Etapa 4 — Escolha do plano."""
    plano_slug = forms.CharField(widget=forms.HiddenInput())
    ref_vendedor = forms.CharField(
        max_length=60,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Codigo do vendedor (opcional)", "class": FIELD_CLASS}),
    )
