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
    username = forms.CharField(max_length=150)
    tipo_documento = forms.ChoiceField(choices=[("cpf", "CPF"), ("cnpj", "CNPJ")])
    documento = forms.CharField(max_length=18)
    data_expiracao = forms.DateField(required=False)
    email = forms.EmailField()
    telefone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all(), required=False)
    nova_empresa_nome = forms.CharField(max_length=150, required=False)
    limite_administradores = forms.IntegerField(required=False)
    limite_operadores = forms.IntegerField(required=False)
    limite_clientes = forms.IntegerField(required=False)

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        if empresa:
            if empresa.clientes.filter(perfil="admin").count() >= empresa.limite_administradores:
                raise forms.ValidationError("Limite de administradores atingido para esta empresa.")
        elif not cleaned_data.get("nova_empresa_nome"):
            raise forms.ValidationError("Informe uma empresa existente ou os dados da nova empresa.")
        return cleaned_data

    def save(self, criado_por=None):
        data = self.cleaned_data
        empresa = data.get("empresa")
        if not empresa:
            empresa = Empresa.objects.create(
                nome=data["nova_empresa_nome"],
                limite_administradores=data.get("limite_administradores") or 0,
                limite_operadores=data.get("limite_operadores") or 0,
                limite_clientes=data.get("limite_clientes") or 0,
            )
        username = slugify(data["username"]) or slugify(data["documento"]) or slugify(data["nome"]) or "user"
        user = User.objects.create_user(
            username=username,
            password=data["password"],
            first_name=data["nome"],
            email=data["email"],
        )
        cliente = Cliente.objects.create(
            usuario=user,
            tipo_documento=data["tipo_documento"],
            documento=data["documento"],
            data_expiracao=data.get("data_expiracao"),
            perfil="admin",
            telefone=data["telefone"],
            empresa=empresa,
            criado_por=criado_por,
        )
        return cliente


class OperadorForm(forms.Form):
    nome = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    tipo_documento = forms.ChoiceField(choices=[("cpf", "CPF"), ("cnpj", "CNPJ")])
    documento = forms.CharField(max_length=18)
    data_expiracao = forms.DateField(required=False)
    email = forms.EmailField(required=False)
    telefone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all())
    administrador_responsavel = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(perfil="admin"),
    )

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        if empresa and empresa.clientes.filter(perfil="operador").count() >= empresa.limite_operadores:
            raise forms.ValidationError("Limite de operadores atingido para esta empresa.")
        admin_resp = cleaned_data.get("administrador_responsavel")
        if admin_resp and admin_resp.empresa != empresa:
            raise forms.ValidationError("Administrador responsável deve pertencer à mesma empresa.")
        return cleaned_data

    def save(self, criado_por=None):
        data = self.cleaned_data
        username = slugify(data["username"]) or slugify(data["documento"]) or slugify(data["nome"]) or "user"
        user = User.objects.create_user(
            username=username,
            password=data["password"],
            first_name=data["nome"],
            email=data.get("email", ""),
        )
        user.is_staff = True
        user.save()
        cliente = Cliente.objects.create(
            usuario=user,
            tipo_documento=data["tipo_documento"],
            documento=data["documento"],
            data_expiracao=data.get("data_expiracao"),
            perfil="operador",
            telefone=data.get("telefone", ""),
            empresa=data["empresa"],
            administrador_responsavel=data["administrador_responsavel"],
            criado_por=criado_por,
        )
        return cliente


class ClienteFormSuper(forms.Form):
    nome = forms.CharField(max_length=150)
    username = forms.CharField(max_length=150)
    tipo_documento = forms.ChoiceField(choices=[("cpf", "CPF"), ("cnpj", "CNPJ")])
    documento = forms.CharField(max_length=18)
    data_expiracao = forms.DateField(required=False)
    email = forms.EmailField(required=False)
    telefone = forms.CharField(max_length=20, required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    empresa = forms.ModelChoiceField(queryset=Empresa.objects.all())
    administrador_responsavel = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(perfil="admin"),
    )
    operador_responsavel = forms.ModelChoiceField(
        queryset=Cliente.objects.filter(perfil="operador"),
    )

    def clean(self):
        cleaned_data = super().clean()
        empresa = cleaned_data.get("empresa")
        if empresa and empresa.clientes.filter(perfil="cliente").count() >= empresa.limite_clientes:
            raise forms.ValidationError("Limite de clientes atingido para esta empresa.")
        admin_resp = cleaned_data.get("administrador_responsavel")
        op_resp = cleaned_data.get("operador_responsavel")
        if admin_resp and admin_resp.empresa != empresa:
            raise forms.ValidationError("Administrador responsável deve pertencer à mesma empresa.")
        if op_resp and op_resp.empresa != empresa:
            raise forms.ValidationError("Operador responsável deve pertencer à mesma empresa.")
        return cleaned_data

    def save(self, criado_por=None):
        data = self.cleaned_data
        username = slugify(data["username"]) or slugify(data["documento"]) or slugify(data["nome"]) or "user"
        user = User.objects.create_user(
            username=username,
            password=data["password"],
            first_name=data["nome"],
            email=data.get("email", ""),
        )
        cliente = Cliente.objects.create(
            usuario=user,
            tipo_documento=data["tipo_documento"],
            documento=data["documento"],
            data_expiracao=data.get("data_expiracao"),
            perfil="cliente",
            telefone=data.get("telefone", ""),
            empresa=data["empresa"],
            administrador_responsavel=data["administrador_responsavel"],
            operador_responsavel=data["operador_responsavel"],
            criado_por=criado_por,
        )
        return cliente
