from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from gestao.models import Empresa, Cliente


class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            "nome",
            "limite_administradores",
            "limite_operadores",
            "limite_clientes",
        ]


class AdministradorForm(forms.Form):
    nome = forms.CharField(max_length=150)
    cpf = forms.CharField(max_length=14)
    email = forms.EmailField()
    telefone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all())

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        if empresa and empresa.clientes.filter(perfil="admin").count() >= empresa.limite_administradores:
            raise forms.ValidationError("Limite de administradores atingido para esta empresa.")
        return cleaned_data

    def save(self, criado_por=None):
        data = self.cleaned_data
        username = slugify(data["cpf"]) or slugify(data["nome"]) or "user"
        user = User.objects.create_user(
            username=username,
            password=data["password"],
            first_name=data["nome"],
            email=data["email"],
        )
        cliente = Cliente.objects.create(
            usuario=user,
            cpf=data["cpf"],
            perfil="admin",
            telefone=data["telefone"],
            empresa=data["empresa"],
            criado_por=criado_por,
        )
        return cliente
