from django import forms
from django.core.validators import RegexValidator
from django.contrib.auth.models import User
from .models import (
    ContaFidelidade,
    ProgramaFidelidade,
    Cliente,
    Aeroporto,
    EmissaoPassagem,
    EmissaoHotel,
    CotacaoVoo,
    CompanhiaAerea,
        Empresa,
)
from django.db import transaction

class ContaFidelidadeForm(forms.ModelForm):
    class Meta:
        model = ContaFidelidade
        fields = ['cliente', 'programa', 'clube_periodicidade', 'pontos_clube_mes', 'valor_assinatura_clube', 'data_inicio_clube', 'validade']


class ProgramaFidelidadeForm(forms.ModelForm):
    class Meta:
        model = ProgramaFidelidade
        fields = ['nome', 'descricao', 'preco_medio_milheiro']
        widgets = {
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'cols': 40,
                'style': 'resize:vertical; max-height:100px;'
            }),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['usuario', 'telefone', 'data_nascimento', 'cpf', 'perfil', 'observacoes', 'ativo']


class NovoClienteForm(forms.ModelForm):
    # username só com dígitos
    username = forms.CharField(
        max_length=150,
        validators=[RegexValidator(r'^\d+$', 'O username deve conter apenas números.')],
        help_text="Use apenas números (ex: CPF sem pontuação ou um ID numérico).",
    )
    password = forms.CharField(widget=forms.PasswordInput)

    # opcionais, ajuste conforme seu template
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)

    # perfil vem escondido (se você quiser sempre criar como cliente)
    perfil = forms.CharField(widget=forms.HiddenInput(), initial="cliente")

    class Meta:
        model = Cliente
        fields = [
            "telefone",
            "data_nascimento",
            "cpf",
            "observacoes",
            "ativo",
            "perfil",
        ]

    def clean_username(self):
        u = self.cleaned_data["username"]
        if User.objects.filter(username=u).exists():
            raise forms.ValidationError("Este username já está em uso.")
        return u


class AeroportoForm(forms.ModelForm):
    class Meta:
        model = Aeroporto
        fields = ['sigla', 'nome']


class EmissaoPassagemForm(forms.ModelForm):
    qtd_escalas = forms.IntegerField(min_value=0, required=False, initial=0)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for f in [
            'qtd_adultos',
            'qtd_criancas',
            'qtd_bebes',
            'qtd_escalas',
        ]:
            self.fields[f].required = False
        self.fields['companhia_aerea'].queryset = CompanhiaAerea.objects.all()

    class Meta:
        model = EmissaoPassagem
        fields = [
            'cliente',
            'programa',
            'aeroporto_partida',
            'aeroporto_destino',
            'data_ida',
            'data_volta',
            'qtd_adultos',
            'qtd_criancas',
            'qtd_bebes',
            'companhia_aerea',
            'localizador',
            'valor_referencia',
            'valor_pago',
            'pontos_utilizados',
            'valor_referencia_pontos',
            'economia_obtida',
            'detalhes',
        ]
        widgets = {
            'data_ida': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'data_volta': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        

class EmissaoHotelForm(forms.ModelForm):
    class Meta:
        model = EmissaoHotel
        fields = [
            'cliente',
            'nome_hotel',
            'check_in',
            'check_out',
            'valor_referencia',
            'valor_pago',
            'economia_obtida',
        ]
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}),
            'check_out': forms.DateInput(attrs={'type': 'date'}),
                  }


class CotacaoVooForm(forms.ModelForm):
    qtd_escalas = forms.IntegerField(min_value=0, required=False, initial=0)
    companhia_aerea = forms.ChoiceField(choices=[], required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['companhia_aerea'].choices = [
            (c.nome, c.nome) for c in CompanhiaAerea.objects.all()
        ]

    class Meta:
        model = CotacaoVoo
        fields = [
            'cliente',
            'companhia_aerea',
            'origem',
            'destino',
            'programa',
            'data_ida',
            'data_volta',
            'qtd_passageiros',
            'classe',
            'observacoes',
            'valor_passagem',
            'taxas',
            'milhas',
            'valor_milheiro',
            'parcelas',
            'juros',
            'desconto',
            'validade',
            'status',
        ]
        labels = {
            'parcelas': 'Número de parcelas sem juros',
        }
        widgets = {
            'data_ida': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'data_volta': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'validade': forms.DateInput(attrs={'type': 'date'}),
        }


class CalculadoraCotacaoForm(forms.Form):
    valor_passagem = forms.DecimalField(max_digits=10, decimal_places=2)
    taxas = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
    milhas = forms.IntegerField(required=False, initial=0)
    valor_milheiro = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
    parcelas = forms.IntegerField(required=False, initial=1)
    juros = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=1)
    desconto = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=1)

class CompanhiaAereaForm(forms.ModelForm):
    class Meta:
        model = CompanhiaAerea
        fields = ["nome", "site_url"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}),
            "site_url": forms.URLInput(attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}),
        }


class EmpresaForm(forms.ModelForm):
    admin_nome = forms.CharField(max_length=150, label="Nome do admin")
    admin_username = forms.CharField(
        max_length=150,
        help_text="Login de acesso do admin da empresa.",
        label="Usuário (login)",
    )
    admin_cpf = forms.CharField(max_length=14, label="CPF do admin")
    admin_email = forms.EmailField(required=False, label="Email do admin")
    admin_password = forms.CharField(
        widget=forms.PasswordInput, label="Senha inicial do admin"
    )

    class Meta:
        model = Empresa
        fields = ["nome", "limite_colaboradores", "ativo"]
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}
            ),
            "limite_colaboradores": forms.NumberInput(
                attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2", "min": 0}
            ),
        }

    def clean_admin_username(self):
        username = self.cleaned_data["admin_username"]
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Já existe um usuário com esse login.")
        return username

    def save(self, *, criado_por):
        data = self.cleaned_data
        with transaction.atomic():
            empresa = super().save(commit=False)
            empresa.save()
            user = User.objects.create_user(
                username=data["admin_username"],
                password=data["admin_password"],
                first_name=data["admin_nome"],
                email=data.get("admin_email", ""),
            )
            user.is_staff = True
            user.save()
            admin_cliente = Cliente.objects.create(
                usuario=user,
                cpf=data["admin_cpf"],
                perfil="admin",
                empresa=empresa,
                criado_por=criado_por,
            )
            empresa.admin = admin_cliente
            empresa.save()
        return empresa