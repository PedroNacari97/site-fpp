from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from gestao.models import Cliente

class UsuarioForm(forms.Form):
    nome_completo = forms.CharField(max_length=150)
    tipo_documento = forms.ChoiceField(choices=[("cpf", "CPF"), ("cnpj", "CNPJ")])
    documento = forms.CharField(max_length=18)
    data_expiracao = forms.DateField(required=False)
    perfil = forms.ChoiceField(choices=[("admin", "Administrador"), ("operador", "Operador"), ("cliente", "cliente")])
    password = forms.CharField(widget=forms.PasswordInput)

    def save(self, criado_por=None, empresa=None):
        nome = self.cleaned_data["nome_completo"]
        documento = self.cleaned_data["documento"]
        username = slugify(documento) or slugify(nome) or "user"
        user = User.objects.create_user(
            username=username,
            password=self.cleaned_data["password"],
            first_name=nome,
        )
        user.is_staff = True
        user.save()
        Cliente.objects.create(
            usuario=user,
            tipo_documento=self.cleaned_data["tipo_documento"],
            documento=documento,
            data_expiracao=self.cleaned_data.get("data_expiracao"),
            perfil=self.cleaned_data["perfil"],
            criado_por=criado_por,
            empresa=empresa,
        )
        return user

class ClientePublicoForm(forms.ModelForm):
    nome = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)

    class Meta:
        model = Cliente
        fields = ['telefone', 'data_nascimento', 'tipo_documento', 'documento', 'data_expiracao', 'observacoes']

    def save(self, commit=True):
        nome = self.cleaned_data['nome']
        username_base = slugify(nome) or 'cliente'
        username = username_base
        i = 1
        while User.objects.filter(username=username).exists():
            username = f"{username_base}{i}"
            i += 1
        password = User.objects.make_random_password()
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=nome,
            email=self.cleaned_data.get('email')
        )
        cliente = super().save(commit=False)
        cliente.usuario = user
        cliente.perfil = 'cliente'
        if commit:
            cliente.save()
        return cliente
