from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction

from gestao.models import Cliente, Empresa
from gestao.utils import (
    generate_unique_username,
    normalize_cpf,
    parse_br_date,
    validate_cpf_digits,
)

User = get_user_model()


class UsuarioForm(forms.Form):
    nome_completo = forms.CharField(max_length=150)
    cpf = forms.CharField(max_length=14)
    perfil = forms.ChoiceField(
        choices=[("admin", "Administrador"), ("operador", "Operador"), ("cliente", "cliente")]
    )
    password = forms.CharField(widget=forms.PasswordInput, required=False)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)

        self.fields["nome_completo"].widget.attrs.update(
            {
                "placeholder": "Ex: Joao da Silva",
                "class": "admin-users__input",
            }
        )
        self.fields["cpf"].widget.attrs.update(
            {
                "placeholder": "000.000.000-00",
                "data-mask": "cpf",
                "inputmode": "numeric",
                "maxlength": "14",
                "class": "admin-users__input",
            }
        )
        self.fields["perfil"].widget.attrs.update({"class": "admin-users__input"})
        self.fields["password"].widget.attrs.update(
            {
                "placeholder": "Digite a senha",
                "class": "admin-users__input",
                "autocomplete": "new-password",
            }
        )
        self.fields["empresa"].widget.attrs.update({"class": "admin-users__input"})
        self.fields["empresa"].empty_label = "Selecione a empresa..."

        if instance:
            self.fields["nome_completo"].initial = (
                instance.usuario.get_full_name()
                or instance.usuario.first_name
                or instance.usuario.username
            )
            self.fields["cpf"].initial = instance.cpf
            self.fields["perfil"].initial = instance.perfil
            self.fields["empresa"].initial = instance.empresa
            self.fields["password"].help_text = "Preencha apenas se quiser alterar a senha."

    def clean(self):
        cleaned = super().clean()
        perfil = cleaned.get("perfil")
        empresa = cleaned.get("empresa")

        if perfil in ["admin", "operador"] and not empresa:
            raise forms.ValidationError("Selecione uma empresa para o usuario.")

        if perfil == "operador" and empresa:
            operadores = Cliente.objects.filter(empresa=empresa, perfil="operador", ativo=True)
            if self.instance:
                operadores = operadores.exclude(pk=self.instance.pk)
            limite = empresa.limite_colaboradores
            if limite and operadores.count() >= limite:
                raise forms.ValidationError(
                    f"O limite de {limite} colaboradores para esta empresa foi atingido. "
                    "Entre em contato para liberar mais acessos."
                )

        if not self.instance and not cleaned.get("password"):
            self.add_error("password", "Informe uma senha para o novo usuario.")

        return cleaned

    def clean_cpf(self):
        cpf = validate_cpf_digits(self.cleaned_data.get("cpf"))
        clientes = Cliente.objects.filter(cpf=cpf)
        if self.instance:
            clientes = clientes.exclude(pk=self.instance.pk)
        if clientes.exists():
            raise forms.ValidationError("Ja existe um usuario com este CPF.")
        return cpf

    def save(self, criado_por=None):
        nome = self.cleaned_data["nome_completo"].strip()
        cpf = normalize_cpf(self.cleaned_data["cpf"])
        empresa = self.cleaned_data.get("empresa")
        password = self.cleaned_data.get("password")

        with transaction.atomic():
            if self.instance:
                user = self.instance.usuario
                user.first_name = nome
                user.is_staff = True
                user.is_active = True
                if password:
                    user.set_password(password)
                user.save()

                self.instance.cpf = cpf
                self.instance.perfil = self.cleaned_data["perfil"]
                self.instance.empresa = empresa
                self.instance.ativo = True
                self.instance.save()
            else:
                username = generate_unique_username()
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=nome,
                )
                user.is_staff = True
                user.save()

                self.instance = Cliente.objects.create(
                    usuario=user,
                    cpf=cpf,
                    perfil=self.cleaned_data["perfil"],
                    empresa=empresa,
                    criado_por=criado_por,
                )

        return self.instance.usuario


class ClientePublicoForm(forms.ModelForm):
    nome = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)

    class Meta:
        model = Cliente
        fields = ["telefone", "data_nascimento", "cpf", "observacoes"]
        widgets = {
            "data_nascimento": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
        }

    def clean_cpf(self):
        cpf = validate_cpf_digits(self.cleaned_data.get("cpf"))
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Ja existe um cliente com este CPF.")
        return cpf

    def clean_data_nascimento(self):
        return parse_br_date(self.cleaned_data.get("data_nascimento"), field_label="Data de nascimento")

    def save(self, commit=True):
        nome = self.cleaned_data["nome"]
        cpf = normalize_cpf(self.cleaned_data.get("cpf"))
        username = generate_unique_username()
        password = User.objects.make_random_password()
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=nome,
                email=self.cleaned_data.get("email"),
            )
            cliente = super().save(commit=False)
            cliente.usuario = user
            cliente.perfil = "cliente"
            cliente.cpf = cpf
            if commit:
                cliente.save()
        return cliente
