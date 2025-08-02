from django import forms
from .models import (
    ContaFidelidade,
    ProgramaFidelidade,
    Cliente,
    Aeroporto,
    EmissaoPassagem,
    EmissaoHotel,
    CotacaoVoo,
    CompanhiaAerea,
)

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
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    email = forms.EmailField(required=False)

    class Meta:
        model = Cliente
        fields = ['telefone', 'data_nascimento', 'cpf', 'perfil', 'observacoes', 'ativo']


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['companhia_aerea'].queryset = CompanhiaAerea.objects.all()

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

class CompanhiaAereaForm(forms.ModelForm):
    class Meta:
        model = CompanhiaAerea
        fields = ["nome", "site_url"]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}),
            "site_url": forms.URLInput(attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}),
        }
