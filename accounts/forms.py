from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from gestao.models import Cliente

class UsuarioForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    perfil = forms.ChoiceField(choices=[('admin', 'Administrador'), ('operador', 'Operador')])

    class Meta:
        model = User
        fields = ['username', 'password', 'first_name', 'last_name', 'email']

    def save(self, criado_por=None, commit=True):
        perfil = self.cleaned_data['perfil']
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.is_staff = True
        if commit:
            user.save()
            Cliente.objects.create(usuario=user, perfil=perfil, criado_por=criado_por)
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
