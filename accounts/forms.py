from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from gestao.models import Cliente, Empresa, Administrador, Operador


class LoginForm(forms.Form):
    """Simple authentication form used by ``UserLoginView``."""

    identifier = forms.CharField(label="Usuário/CPF")
    password = forms.CharField(label="Senha", widget=forms.PasswordInput)

class UsuarioForm(forms.Form):
    nome_completo = forms.CharField(max_length=150)
    cpf = forms.CharField(max_length=14)
    perfil = forms.ChoiceField(choices=[("admin", "Administrador"), ("operador", "Operador")])
    password = forms.CharField(widget=forms.PasswordInput)
    acesso_ate = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False)
    nova_empresa_nome = forms.CharField(required=False, label="Nova empresa")
    limite_operadores = forms.IntegerField(required=False, label="Limite de operadores")
    limite_clientes = forms.IntegerField(required=False, label="Limite de clientes")

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.user and not self.user.is_superuser:
            admin = Administrador.objects.filter(usuario=self.user).first()
            if admin:
                self.fields['empresa'].queryset = Empresa.objects.filter(id=admin.empresa_id)
                self.fields['empresa'].initial = admin.empresa
                self.fields['empresa'].disabled = True
                self.fields['nova_empresa_nome'].widget = forms.HiddenInput()
                self.fields['limite_operadores'].widget = forms.HiddenInput()
                self.fields['limite_clientes'].widget = forms.HiddenInput()
        else:
            self.fields['empresa'].queryset = Empresa.objects.all()

    def save(self, criado_por=None):
        nome = self.cleaned_data["nome_completo"]
        cpf = self.cleaned_data["cpf"]
        username = slugify(cpf) or slugify(nome) or "user"
        user = User.objects.create_user(
            username=username,
            password=self.cleaned_data["password"],
            first_name=nome,
        )
        perfil = self.cleaned_data["perfil"]
        user.is_staff = perfil in ["admin", "operador"]
        user.save()
        Cliente.objects.create(
            usuario=user,
            cpf=cpf,
            perfil=perfil,
            criado_por=criado_por,
        )
        if perfil == "admin":
            empresa = self.cleaned_data.get("empresa")
            if not empresa:
                empresa = Empresa.objects.create(
                    nome=self.cleaned_data.get("nova_empresa_nome") or nome,
                    limite_operadores=self.cleaned_data.get("limite_operadores"),
                    limite_clientes=self.cleaned_data.get("limite_clientes"),
                )
            Administrador.objects.create(
                usuario=user,
                empresa=empresa,
                acesso_ate=self.cleaned_data.get("acesso_ate"),
            )
        elif perfil == "operador":
            admin = Administrador.objects.filter(usuario=criado_por).first()
            empresa = admin.empresa if admin else None
            Operador.objects.create(
                usuario=user,
                admin=admin,
                empresa=empresa,
            )
        return user

class ClientePublicoForm(forms.ModelForm):
    nome = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)

    class Meta:
        model = Cliente
        fields = ['telefone', 'data_nascimento', 'cpf', 'observacoes']

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
