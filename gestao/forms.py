from django import forms
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from gestao.utils import (
    generate_unique_username,
    normalize_cpf,
    parse_br_date,
    validate_cpf_digits,
)

from .models import (
    ContaFidelidade,
    ContaAdministrada,
    ProgramaFidelidade,
    Cliente,
    Aeroporto,
    EmissaoPassagem,
    EmissaoHotel,
    CotacaoVoo,
    CompanhiaAerea,
    Empresa,
    EmissorParceiro,
)


User = get_user_model()

class ContaFidelidadeForm(forms.ModelForm):
    class Meta:
        model = ContaFidelidade
        fields = [
            "cliente",
            "conta_administrada",
            "programa",
            "login_programa",
            "senha_programa",
            "titular_programa_info",
            "observacoes_programa",
            "clube_periodicidade",
            "pontos_clube_mes",
            "valor_assinatura_clube",
            "data_inicio_clube",
            "validade",
            "quantidade_cpfs_disponiveis",
        ]
        widgets = {
            "data_inicio_clube": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
            "validade": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
            "login_programa": forms.TextInput(
                attrs={
                    "placeholder": "Login do titular",
                    "class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2",
                }
            ),
            "senha_programa": forms.PasswordInput(
                render_value=True,
                attrs={
                    "placeholder": "Senha do titular",
                    "class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2",
                },
            ),
            "titular_programa_info": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Dados adicionais do titular (nome, CPF, observações de resgate)",
                    "class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2",
                    "style": "resize:vertical;",
                }
            ),
            "observacoes_programa": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Observações gerais sobre o uso desta conta (limitações, preferências de resgate, etc.)",
                    "class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2",
                    "style": "resize:vertical;",
                }
            ),
            "quantidade_cpfs_disponiveis": forms.NumberInput(
                attrs={
                    "class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2",
                    "min": 0,
                    "placeholder": "Deixe vazio para ilimitado",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        cliente_qs = Cliente.objects.filter(perfil="cliente", ativo=True).select_related("usuario")
        conta_adm_qs = ContaAdministrada.objects.filter(ativo=True)
        if empresa:
            cliente_qs = cliente_qs.filter(empresa=empresa)
            conta_adm_qs = conta_adm_qs.filter(empresa=empresa)
        if self.instance and self.instance.pk:
            cliente_qs = cliente_qs | Cliente.objects.filter(pk=self.instance.cliente_id)
            conta_adm_qs = conta_adm_qs | ContaAdministrada.objects.filter(pk=self.instance.conta_administrada_id)
        self.fields["cliente"].queryset = cliente_qs
        self.fields["conta_administrada"].queryset = conta_adm_qs
        self.fields["login_programa"].label = "Login (titular do programa)"
        self.fields["senha_programa"].label = "Senha (titular do programa)"
        self.fields["titular_programa_info"].label = "Dados do titular"

    def clean(self):
        cleaned = super().clean()
        cliente = cleaned.get("cliente")
        conta_adm = cleaned.get("conta_administrada")
        if bool(cliente) == bool(conta_adm):
            raise forms.ValidationError("Selecione um cliente ou uma conta administrada, mas não ambos.")
        return cleaned

    def clean_data_inicio_clube(self):
        return parse_br_date(self.cleaned_data.get("data_inicio_clube"), field_label="Data de início do clube")

    def clean_validade(self):
        return parse_br_date(self.cleaned_data.get("validade"), field_label="Validade")


class ProgramaFidelidadeForm(forms.ModelForm):
    class Meta:
        model = ProgramaFidelidade
        fields = [
            "nome",
            "descricao",
            "preco_medio_milheiro",
            "quantidade_cpfs_disponiveis",
            "tipo",
            "programa_base",
        ]
        widgets = {
            'descricao': forms.Textarea(attrs={
                'rows': 4,
                'cols': 40,
                'style': 'resize:vertical; max-height:100px;'
            }),
        }
        labels = {
            "preco_medio_milheiro": "Preço médio do milheiro (R$)",
            "quantidade_cpfs_disponiveis": "Quantidade de CPFs disponíveis por programa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_qs = ProgramaFidelidade.objects.filter(tipo=ProgramaFidelidade.TIPO_PRINCIPAL)
        if self.instance and self.instance.pk:
            base_qs = base_qs.exclude(pk=self.instance.pk)
        self.fields["programa_base"].queryset = base_qs
        self.fields["programa_base"].required = False


class ContaAdministradaForm(forms.ModelForm):
    class Meta:
        model = ContaAdministrada
        fields = ["nome", "observacoes", "ativo"]
        widgets = {
            "observacoes": forms.Textarea(
                attrs={
                    "rows": 3,
                    "class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2",
                }
            ),
            "nome": forms.TextInput(
                attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}
            ),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['usuario', 'telefone', 'data_nascimento', 'cpf', 'perfil', 'observacoes', 'ativo']
        widgets = {
            "data_nascimento": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
        }

    def clean_cpf(self):
        cpf = validate_cpf_digits(self.cleaned_data.get("cpf"))
        if Cliente.objects.exclude(pk=self.instance.pk).filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def clean_data_nascimento(self):
        return parse_br_date(self.cleaned_data.get("data_nascimento"), field_label="Data de nascimento")


class NovoClienteForm(forms.ModelForm):
    password = forms.CharField(widget=forms.PasswordInput)
    first_name = forms.CharField(required=False)
    last_name = forms.CharField(required=False)
    email = forms.EmailField(required=False)
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
        widgets = {
            "data_nascimento": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
        }

    def clean_cpf(self):
        cpf = validate_cpf_digits(self.cleaned_data.get("cpf"))
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def clean_data_nascimento(self):
        return parse_br_date(self.cleaned_data.get("data_nascimento"), field_label="Data de nascimento")


class AeroportoForm(forms.ModelForm):
    class Meta:
        model = Aeroporto
        fields = ['sigla', 'nome']


class EmissaoPassagemForm(forms.ModelForm):
    tipo_emissao = forms.ChoiceField(
        choices=(
            ("cliente", "Conta do Cliente"),
            ("administrada", "Conta Administrada"),
            ("parceiro", "Emissor Parceiro"),
        ),
        initial="cliente",
    )
    conta_administrada = forms.ModelChoiceField(
        queryset=ContaAdministrada.objects.none(), required=False
    )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        for f in [
            'qtd_adultos',
            'qtd_criancas',
            'qtd_bebes',
        ]:
            self.fields[f].required = False
        self.fields['companhia_aerea'].queryset = CompanhiaAerea.objects.all()
        clientes_qs = Cliente.objects.filter(perfil="cliente", ativo=True).select_related("usuario")
        contas_adm_qs = ContaAdministrada.objects.filter(ativo=True)
        if empresa:
            clientes_qs = clientes_qs.filter(empresa=empresa)
            contas_adm_qs = contas_adm_qs.filter(empresa=empresa)
            self.fields["emissor_parceiro"].queryset = EmissorParceiro.objects.filter(
                empresa=empresa, ativo=True
            )
        else:
            self.fields["emissor_parceiro"].queryset = EmissorParceiro.objects.filter(ativo=True)
        if self.instance and self.instance.pk:
            clientes_qs = clientes_qs | Cliente.objects.filter(pk=self.instance.cliente_id)
            contas_adm_qs = contas_adm_qs | ContaAdministrada.objects.filter(pk=self.instance.conta_administrada_id)
        self.fields["cliente"].queryset = clientes_qs
        self.fields["conta_administrada"].queryset = contas_adm_qs

        selected_tipo = self.data.get("tipo_emissao")
        if not selected_tipo:
            if getattr(self.instance, "emissor_parceiro_id", None):
                selected_tipo = "parceiro"
            elif getattr(self.instance, "conta_administrada_id", None):
                selected_tipo = "administrada"
            else:
                selected_tipo = "cliente"
        self.initial.setdefault("tipo_emissao", selected_tipo)
        self.fields["cliente"].required = True
        self.fields["conta_administrada"].required = selected_tipo == "administrada"

        titular_id = None
        emissor_parceiro_id = self.data.get("emissor_parceiro") or getattr(
            self.instance, "emissor_parceiro_id", None
        )
        if selected_tipo == "administrada":
            titular_id = self.data.get("conta_administrada") or getattr(self.instance, "conta_administrada_id", None)
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__conta_administrada_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()
        elif selected_tipo == "parceiro":
            if empresa:
                programas_qs = ProgramaFidelidade.objects.filter(
                    contafidelidade__cliente__empresa=empresa
                ) | ProgramaFidelidade.objects.filter(
                    contafidelidade__conta_administrada__empresa=empresa
                )
            else:
                programas_qs = ProgramaFidelidade.objects.all()
        else:
            titular_id = self.data.get("cliente") or getattr(self.instance, "cliente_id", None)
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__cliente_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()

        programas_qs = programas_qs.distinct()
        if self.instance and self.instance.programa_id and not programas_qs.filter(id=self.instance.programa_id).exists():
            programas_qs = programas_qs | ProgramaFidelidade.objects.filter(id=self.instance.programa_id)
        self.fields["programa"].queryset = programas_qs.distinct()

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo_emissao")
        cliente = cleaned.get("cliente")
        conta_adm = cleaned.get("conta_administrada")
        total_passageiros = sum(
            int(cleaned.get(field) or 0) for field in ("qtd_adultos", "qtd_criancas", "qtd_bebes")
        )
        if total_passageiros <= 0:
            raise forms.ValidationError("Informe pelo menos um passageiro no total.")
        if not cliente:
            raise forms.ValidationError("Selecione o cliente que irá viajar.")
        emissor_parceiro = cleaned.get("emissor_parceiro")
        if tipo == "administrada":
            if not conta_adm:
                raise forms.ValidationError("Selecione uma conta administrada para usar pontos ou escolha 'Conta de Cliente'.")
            if cleaned.get("pontos_utilizados") and cleaned.get("valor_milheiro_parceiro") in (None, ""):
                raise forms.ValidationError("Informe o valor do milheiro usado na conta administrada.")
        elif tipo != "parceiro":
            cleaned["conta_administrada"] = None
        if tipo == "parceiro":
            if not emissor_parceiro:
                raise forms.ValidationError("Selecione o emissor parceiro para este tipo de emissão.")
            if cleaned.get("valor_milheiro_parceiro") in (None, "") and cleaned.get("pontos_utilizados"):
                raise forms.ValidationError("Informe o valor do milheiro negociado com o emissor parceiro.")
            cleaned["conta_administrada"] = None
        else:
            cleaned["emissor_parceiro"] = None
        return cleaned

    class Meta:
        model = EmissaoPassagem
        fields = [
            'tipo_emissao',
            'cliente',
            'conta_administrada',
            'programa',
            'emissor_parceiro',
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
            'valor_taxas',
            'pontos_utilizados',
            'valor_referencia_pontos',
            'economia_obtida',
            'detalhes',
            'valor_milheiro_parceiro',
            'valor_venda_final',
            'lucro',
        ]
        widgets = {
            'data_ida': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'data_volta': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'valor_referencia_pontos': forms.NumberInput(attrs={'step': '0.01', 'readonly': 'readonly'}),
            'valor_milheiro_parceiro': forms.NumberInput(attrs={'step': '0.01'}),
            'valor_venda_final': forms.NumberInput(attrs={'step': '0.01'}),
            'lucro': forms.NumberInput(attrs={'step': '0.01', 'readonly': 'readonly'}),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        clientes_qs = Cliente.objects.filter(perfil="cliente", ativo=True).select_related("usuario")
        if self.instance and self.instance.pk:
            clientes_qs = clientes_qs | Cliente.objects.filter(pk=self.instance.cliente_id)
        self.fields["cliente"].queryset = clientes_qs


class EmissorParceiroForm(forms.ModelForm):
    class Meta:
        model = EmissorParceiro
        fields = ["nome", "programas", "ativo", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        if empresa:
            programas_qs = ProgramaFidelidade.objects.filter(
                Q(contafidelidade__cliente__empresa=empresa)
                | Q(contafidelidade__conta_administrada__empresa=empresa)
            ).distinct()
        else:
            programas_qs = ProgramaFidelidade.objects.all()
        self.fields["programas"].queryset = programas_qs


class CotacaoVooForm(forms.ModelForm):
    companhia_aerea = forms.ChoiceField(choices=[], required=False)
    tipo_titular = forms.ChoiceField(
        choices=(("cliente", "Conta de Cliente"), ("administrada", "Conta Administrada")),
        initial="cliente",
    )
    conta_administrada = forms.ModelChoiceField(
        queryset=ContaAdministrada.objects.none(), required=False
    )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        self.fields['companhia_aerea'].choices = [
            (c.nome, c.nome) for c in CompanhiaAerea.objects.all()
        ]
        clientes_qs = Cliente.objects.filter(perfil="cliente", ativo=True).select_related("usuario")
        contas_adm_qs = ContaAdministrada.objects.filter(ativo=True)
        if empresa:
            clientes_qs = clientes_qs.filter(empresa=empresa)
            contas_adm_qs = contas_adm_qs.filter(empresa=empresa)
        if self.instance and self.instance.pk:
            clientes_qs = clientes_qs | Cliente.objects.filter(pk=self.instance.cliente_id)
            contas_adm_qs = contas_adm_qs | ContaAdministrada.objects.filter(pk=self.instance.conta_administrada_id)
        self.fields["cliente"].queryset = clientes_qs
        self.fields["conta_administrada"].queryset = contas_adm_qs

        selected_tipo = self.data.get("tipo_titular") or ("administrada" if getattr(self.instance, "conta_administrada_id", None) else "cliente")
        self.initial.setdefault("tipo_titular", selected_tipo)
        self.fields["cliente"].required = True
        self.fields["conta_administrada"].required = selected_tipo == "administrada"

        titular_id = None
        if selected_tipo == "administrada":
            titular_id = self.data.get("conta_administrada") or getattr(self.instance, "conta_administrada_id", None)
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__conta_administrada_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()
        else:
            titular_id = self.data.get("cliente") or getattr(self.instance, "cliente_id", None)
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__cliente_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()

        if self.instance and self.instance.programa_id and not programas_qs.filter(id=self.instance.programa_id).exists():
            programas_qs = programas_qs | ProgramaFidelidade.objects.filter(id=self.instance.programa_id)
        self.fields["programa"].queryset = programas_qs.distinct()

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo_titular")
        cliente = cleaned.get("cliente")
        conta_adm = cleaned.get("conta_administrada")
        if not cliente:
            raise forms.ValidationError("Selecione o cliente que irá viajar.")
        if tipo == "administrada":
            if not conta_adm:
                raise forms.ValidationError("Selecione uma conta administrada para usar pontos ou escolha 'Conta de Cliente'.")
        else:
            cleaned["conta_administrada"] = None
        return cleaned

    class Meta:
        model = CotacaoVoo
        fields = [
            'tipo_titular',
            'cliente',
            'conta_administrada',
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

    def clean_admin_cpf(self):
        cpf = validate_cpf_digits(self.cleaned_data.get("admin_cpf"), field_label="CPF do admin")
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def save(self, *, criado_por):
        data = self.cleaned_data
        with transaction.atomic():
            empresa = super().save(commit=False)
            empresa.save()
            user = User.objects.create_user(
                username=generate_unique_username(),
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
