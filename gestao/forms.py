from django import forms
from .models import (
    ContaFidelidade,
    ProgramaFidelidade,
    Cliente,
    Aeroporto,
    EmissaoPassagem,
)

class ContaFidelidadeForm(forms.ModelForm):
    class Meta:
        model = ContaFidelidade
        fields = ['cliente', 'programa', 'clube_periodicidade', 'pontos_clube_mes', 'valor_assinatura_clube', 'data_inicio_clube', 'validade']


class ProgramaFidelidadeForm(forms.ModelForm):
    class Meta:
        model = ProgramaFidelidade
        fields = ['nome', 'descricao']


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['usuario', 'telefone', 'data_nascimento', 'cpf', 'perfil', 'observacoes', 'ativo']


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
            'valor_referencia',
            'valor_pago',
            'pontos_utilizados',
            'valor_referencia_pontos',
            'economia_obtida',
            'detalhes',
        ]
        widgets = {
            'data_ida': forms.DateInput(attrs={'type': 'date'}),
            'data_volta': forms.DateInput(attrs={'type': 'date'}),
        }
