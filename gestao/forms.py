from django import forms
from .models import (
    ContaFidelidade,
    ProgramaFidelidade,
    Cliente,
    Aeroporto,
    EmissaoPassagem,
    EmissaoHotel,
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
    class Meta:
        model = EmissaoPassagem
        fields = [
            'cliente',
            'programa',
            'aeroporto_partida',
            'aeroporto_destino',
            'data_ida',
            'data_volta',
            'qtd_passageiros',
            'companhia_aerea',
            'localizador',
            'valor_referencia',
            'valor_pago',
            'pontos_utilizados',
            'valor_referencia_pontos',
            'economia_obtida',
            'detalhes',
            'companhia_aerea',
            'localizador',
        ]
        widgets = {
            'data_ida': forms.DateInput(attrs={'type': 'date'}),
            'data_volta': forms.DateInput(attrs={'type': 'date'}),
        }
<<<<<<< HEAD
        
=======

>>>>>>> dc8bb7d0f6d16a3cf1b645b0cfa9f1ad1d83a070

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
<<<<<<< HEAD
                  }
=======
        }
>>>>>>> dc8bb7d0f6d16a3cf1b645b0cfa9f1ad1d83a070
