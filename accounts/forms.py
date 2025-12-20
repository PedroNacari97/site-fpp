from django import forms
from django.contrib.auth.models import User
from django.utils.text import slugify
from gestao.models import Cliente, Empresa

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

    def save(self, criado_por=None):
        nome = self.cleaned_data["nome_completo"]
        cpf = self.cleaned_data["cpf"]
        username = slugify(cpf) or slugify(nome) or "user"
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
