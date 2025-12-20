from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from gestao.models import Cliente, Empresa
from gestao.utils import generate_unique_username, normalize_cpf

User = get_user_model()

class UsuarioForm(forms.Form):
    nome_completo = forms.CharField(max_length=150)
    cpf = forms.CharField(max_length=14)
    perfil = forms.ChoiceField(choices=[("admin", "Administrador"), ("operador", "Operador"), ("cliente", "cliente")])
    password = forms.CharField(widget=forms.PasswordInput)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False)

    def clean(self):
        cleaned = super().clean()
        perfil = cleaned.get("perfil")
        empresa = cleaned.get("empresa")
        if perfil in ["admin", "operador"] and not empresa:
            raise forms.ValidationError("Selecione uma empresa para o usuário.")
        if perfil == "operador" and empresa:
            operadores = Cliente.objects.filter(empresa=empresa, perfil="operador").count()
            limite = empresa.limite_colaboradores
            if limite and operadores >= limite:
                raise forms.ValidationError(
                    f"O limite de {limite} colaboradores para esta empresa já foi atingido."
                )
        return cleaned

    def clean_cpf(self):
        cpf = normalize_cpf(self.cleaned_data.get("cpf"))
        if not cpf:
            raise forms.ValidationError("CPF é obrigatório.")
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def save(self, criado_por=None):
        nome = self.cleaned_data["nome_completo"]
        cpf = self.cleaned_data["cpf"]
        username = generate_unique_username()
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=self.cleaned_data["password"],
                first_name=nome,
            )
            user.is_staff = True
            user.save()
            empresa = self.cleaned_data.get("empresa")
            Cliente.objects.create(
                usuario=user,
                cpf=cpf,
                perfil=self.cleaned_data["perfil"],
                empresa=empresa,
                criado_por=criado_por,
            )
        return user

class ClientePublicoForm(forms.ModelForm):
    nome = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)

    class Meta:
        model = Cliente
        fields = ['telefone', 'data_nascimento', 'cpf', 'observacoes']

    def clean_cpf(self):
        cpf = normalize_cpf(self.cleaned_data.get("cpf"))
        if not cpf:
            raise forms.ValidationError("CPF é obrigatório.")
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def save(self, commit=True):
        nome = self.cleaned_data['nome']
        cpf = normalize_cpf(self.cleaned_data.get("cpf"))
        username = generate_unique_username()
        password = User.objects.make_random_password()
        with transaction.atomic():
            user = User.objects.create_user(
                username=username,
                password=password,
                first_name=nome,
                email=self.cleaned_data.get('email')
            )
            cliente = super().save(commit=False)
            cliente.usuario = user
            cliente.perfil = 'cliente'
            cliente.cpf = cpf
            if commit:
                cliente.save()
        return cliente
