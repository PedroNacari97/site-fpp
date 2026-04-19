from django import forms
from django.contrib.auth import get_user_model
from django.core.validators import MaxLengthValidator
from django.db import transaction
from django.db.models import Q
from uuid import uuid4

from gestao.utils import (
    generate_unique_username,
    normalize_cpf,
    parse_br_date,
    validate_cpf_digits,
)
from gestao.services.aeroporto_localizacao import infer_airport_location

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
    AlertaViagem,
    PassageiroFrequente,
    AcompanhamentoPassagem,
    InteresseViagemCliente,
    DocumentoPlataforma,
    CartaoCliente,
    ProgramaSalaVip,
)


User = get_user_model()

MONTH_CHOICES = [
    ("1", "Jan"),
    ("2", "Fev"),
    ("3", "Mar"),
    ("4", "Abr"),
    ("5", "Mai"),
    ("6", "Jun"),
    ("7", "Jul"),
    ("8", "Ago"),
    ("9", "Set"),
    ("10", "Out"),
    ("11", "Nov"),
    ("12", "Dez"),
]

DAY_CHOICES = [(str(day), f"{day:02d}") for day in range(1, 32)]

SEMESTER_CHOICES = [
    ("1", "1o semestre"),
    ("2", "2o semestre"),
]

TIMEZONE_OFFSET_CHOICES = [(str(offset), f"{offset:+d}h") for offset in range(-12, 15)]


def _parse_duration_to_minutes(value):
    raw_value = str(value or "").strip()
    if not raw_value:
        return 0
    try:
        parts = raw_value.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
    except (TypeError, ValueError, IndexError):
        raise forms.ValidationError("Informe o tempo de voo no formato HH:MM.")
    if hours < 0 or minutes < 0 or minutes > 59:
        raise forms.ValidationError("Informe um tempo de voo valido.")
    return (hours * 60) + minutes


def _format_duration_from_minutes(value):
    total_minutes = int(value or 0)
    if total_minutes <= 0:
        return ""
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def _generate_internal_cpf():
    while True:
        candidate = f"9{uuid4().int % 10**10:010d}"
        if not Cliente.objects.filter(cpf=candidate).exists():
            return candidate


def _split_full_name(value):
    normalized = " ".join(str(value or "").split())
    if not normalized:
        return "", ""
    first_name, _, last_name = normalized.partition(" ")
    return first_name, last_name


def _format_cep(value):
    digits = normalize_cpf(value)[:8]
    if not digits:
        return ""
    if len(digits) != 8:
        raise forms.ValidationError("CEP deve conter 8 digitos.")
    return f"{digits[:5]}-{digits[5:]}"


def _format_uf(value):
    return "".join(ch for ch in str(value or "").upper() if ch.isalpha())[:2]


def _configure_masked_cpf_field(field):
    field.max_length = 14
    field.validators = [
        validator for validator in field.validators
        if not isinstance(validator, MaxLengthValidator)
    ]
    field.validators.append(MaxLengthValidator(14))
    field.widget.attrs.update({
        "placeholder": "000.000.000-00",
        "data-mask": "cpf",
        "inputmode": "numeric",
        "maxlength": "14",
    })


class ContaFidelidadeForm(forms.ModelForm):
    clube_ativo = forms.BooleanField(required=False)

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
        self.fields["cliente"].empty_label = "Selecione o cliente"
        self.fields["conta_administrada"].empty_label = "Selecione"
        self.fields["programa"].empty_label = "Selecione o programa"
        self.fields["clube_periodicidade"].label = "Periodicidade da cobrança"
        self.fields["pontos_clube_mes"].label = "Pontos por recorrência"
        self.fields["valor_assinatura_clube"].label = "Valor por recorrência"
        self.fields["data_inicio_clube"].label = "Data de início da recorrência"
        self.fields["clube_periodicidade"].required = False
        self.fields["clube_periodicidade"].choices = [
            ("", "Selecione o tipo"),
            ("anual", "Anual"),
            ("semestral", "Semestral"),
            ("trimestral", "Trimestral"),
            ("mensal", "Mensal"),
        ]
        clube_ativo = False
        if self.is_bound:
            clube_ativo = self.data.get("clube_ativo") in ("on", "true", "1", "True")
        elif self.instance and self.instance.pk:
            clube_ativo = self.instance.clube_periodicidade != "nenhum"
        self.fields["clube_ativo"].initial = clube_ativo
        self.fields["login_programa"].widget.attrs.update({"placeholder": "Digite o login"})
        self.fields["senha_programa"].widget.attrs.update({"placeholder": "Digite a senha"})
        self.fields["titular_programa_info"].widget.attrs.update(
            {"placeholder": "Nome completo, CPF, telefone, e-mail, observacoes de resgate..."}
        )
        self.fields["observacoes_programa"].widget.attrs.update(
            {"placeholder": "Limitacoes, preferencias de resgate, regras especiais, etc..."}
        )
        self.fields["pontos_clube_mes"].widget.attrs.update({"placeholder": "0", "min": 0})
        self.fields["valor_assinatura_clube"].widget.attrs.update(
            {"placeholder": "0", "min": 0, "step": "0.01"}
        )

    def clean(self):
        cleaned = super().clean()
        cliente = cleaned.get("cliente")
        conta_adm = cleaned.get("conta_administrada")
        clube_ativo = cleaned.get("clube_ativo")
        if bool(cliente) == bool(conta_adm):
            raise forms.ValidationError("Selecione um cliente ou uma conta administrada, mas não ambos.")
        if clube_ativo:
            if not cleaned.get("clube_periodicidade"):
                self.add_error("clube_periodicidade", "Selecione o tipo de assinatura.")
            if not cleaned.get("data_inicio_clube"):
                self.add_error("data_inicio_clube", "Informe a data de início da recorrência.")
        else:
            cleaned["clube_periodicidade"] = "nenhum"
            cleaned["pontos_clube_mes"] = cleaned.get("pontos_clube_mes") or 0
            cleaned["valor_assinatura_clube"] = cleaned.get("valor_assinatura_clube") or 0
            cleaned["data_inicio_clube"] = None
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
            "limite_cpfs",
            "tipo_regra_reset",
            "dias_reset",
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
            "limite_cpfs": "Limite de CPFs por conta",
            "tipo_regra_reset": "Regra de liberação de CPF",
            "dias_reset": "Dias para nova liberação",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        base_qs = ProgramaFidelidade.objects.filter(tipo=ProgramaFidelidade.TIPO_PRINCIPAL)
        if self.instance and self.instance.pk:
            base_qs = base_qs.exclude(pk=self.instance.pk)
        self.fields["programa_base"].queryset = base_qs
        self.fields["programa_base"].required = False
        self.fields["nome"].widget.attrs.update({
            "placeholder": "Ex: AAdvantage",
            "autocomplete": "off",
        })
        self.fields["descricao"].widget.attrs.update({
            "placeholder": "Ex: Programa da American Airlines",
            "style": "",
        })
        self.fields["preco_medio_milheiro"].widget.attrs.update({
            "placeholder": "Ex: 15.00",
            "step": "0.01",
            "min": "0",
        })
        self.fields["quantidade_cpfs_disponiveis"].widget.attrs.update({
            "placeholder": "Ex: 10",
            "min": "0",
        })
        self.fields["limite_cpfs"].widget.attrs.update({
            "placeholder": "Ex: 2",
            "min": "0",
        })
        self.fields["dias_reset"].widget.attrs.update({
            "placeholder": "Ex: 30",
            "min": "0",
        })
        self.fields["tipo_regra_reset"].choices = [("", "Selecione..."), *self.fields["tipo_regra_reset"].choices]
        self.fields["tipo"].choices = [("", "Selecione..."), *self.fields["tipo"].choices]
        self.fields["programa_base"].empty_label = "Selecione..."


class ProgramaFidelidadeForm(ProgramaFidelidadeForm):
    remover_logo = forms.BooleanField(required=False)

    class Meta(ProgramaFidelidadeForm.Meta):
        fields = [
            "nome",
            "logo",
            "descricao",
            "preco_medio_milheiro",
            "quantidade_cpfs_disponiveis",
            "limite_cpfs",
            "tipo_regra_reset",
            "dias_reset",
            "tipo",
            "programa_base",
        ]
        widgets = {
            **ProgramaFidelidadeForm.Meta.widgets,
            "logo": forms.FileInput(
                attrs={
                    "accept": ".png,image/png",
                }
            ),
        }
        labels = {
            **ProgramaFidelidadeForm.Meta.labels,
            "logo": "Logo do programa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["remover_logo"].initial = False
        self.fields["logo"].widget.attrs.update({
            "class": "points-program-form__file-input",
        })
        self.fields["remover_logo"].widget.attrs.update({
            "class": "points-program-form__checkbox",
        })

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if not logo:
            return logo

        if getattr(logo, "size", 0) > 50 * 1024:
            raise forms.ValidationError("Envie uma logo com no maximo 50KB.")

        content_type = getattr(logo, "content_type", "")
        if content_type and content_type != "image/png":
            raise forms.ValidationError("Envie a logo em PNG com fundo transparente.")

        return logo

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.cleaned_data.get("remover_logo") and not self.cleaned_data.get("logo") and instance.logo:
            instance.logo.delete(save=False)
            instance.logo = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


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
        fields = [
            "usuario",
            "telefone",
            "data_nascimento",
            "cpf",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "perfil",
            "tipo_cliente",
            "programas_concierge",
            "razao_social",
            "cnpj",
            "observacoes",
            "ativo",
        ]
        widgets = {
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
            "cpf": forms.TextInput(
                attrs={
                    "placeholder": "000.000.000-00",
                    "data-mask": "cpf",
                    "inputmode": "numeric",
                    "maxlength": "14",
                }
            ),
            "data_nascimento": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
            "cep": forms.TextInput(
                attrs={
                    "placeholder": "00000-000",
                    "data-mask": "cep",
                    "inputmode": "numeric",
                    "maxlength": "9",
                }
            ),
            "endereco": forms.TextInput(attrs={"placeholder": "Rua, avenida..."}),
            "numero": forms.TextInput(attrs={"placeholder": "Numero"}),
            "complemento": forms.TextInput(attrs={"placeholder": "Apto, bloco, referencia..."}),
            "bairro": forms.TextInput(attrs={"placeholder": "Bairro"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Cidade"}),
            "estado": forms.TextInput(attrs={"placeholder": "UF", "maxlength": "2"}),
        }
        labels = {
            "cep": "CEP",
            "endereco": "Rua / Logradouro",
            "numero": "Numero",
            "complemento": "Complemento",
            "bairro": "Bairro",
            "cidade": "Cidade",
            "estado": "UF",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_masked_cpf_field(self.fields["cpf"])
        for field_name in (
            "cpf",
            "telefone",
            "data_nascimento",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "observacoes",
            "programas_concierge",
            "razao_social",
            "cnpj",
        ):
            self.fields[field_name].required = False
        self.fields["ativo"].initial = True
        self.fields["tipo_cliente"].label = "Tipo de cliente"
        self.fields["tipo_cliente"].help_text = (
            "Passageiro direto = cliente final. Concierge = VIP com gestao completa. "
            "Conta administrada = titular de conta de milhas cedida. Intermediario = agencia revendedora."
        )
        self.fields["programas_concierge"].widget.attrs.setdefault(
            "placeholder", "Ex: Smiles, TudoAzul, LATAM Pass"
        )
        self.fields["razao_social"].widget.attrs.setdefault("placeholder", "Razao social da agencia parceira")
        self.fields["cnpj"].widget.attrs.setdefault("placeholder", "00.000.000/0000-00")

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf") or getattr(self.instance, "cpf", "") or _generate_internal_cpf()
        cpf = validate_cpf_digits(cpf)
        if Cliente.objects.exclude(pk=self.instance.pk).filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def clean_data_nascimento(self):
        return parse_br_date(self.cleaned_data.get("data_nascimento"), field_label="Data de nascimento")

    def clean_cep(self):
        return _format_cep(self.cleaned_data.get("cep"))

    def clean_estado(self):
        return _format_uf(self.cleaned_data.get("estado"))


class NovoClienteForm(forms.ModelForm):
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Digite a senha"})
    )
    confirm_password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={"placeholder": "Confirme a senha"})
    )
    full_name = forms.CharField(
        required=False,
        max_length=300,
        widget=forms.TextInput(attrs={"placeholder": "Digite o nome completo"}),
    )
    first_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Nome"}),
    )
    last_name = forms.CharField(
        required=False,
        max_length=150,
        widget=forms.TextInput(attrs={"placeholder": "Sobrenome"}),
    )
    email = forms.EmailField(required=False, widget=forms.EmailInput(attrs={"placeholder": "exemplo@email.com"}))
    perfil = forms.CharField(widget=forms.HiddenInput(), initial="cliente")

    class Meta:
        model = Cliente
        fields = [
            "telefone",
            "data_nascimento",
            "cpf",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "tipo_cliente",
            "programas_concierge",
            "razao_social",
            "cnpj",
            "observacoes",
            "ativo",
            "perfil",
        ]
        widgets = {
            "telefone": forms.TextInput(attrs={"placeholder": "(00) 00000-0000"}),
            "cpf": forms.TextInput(
                attrs={
                    "placeholder": "000.000.000-00",
                    "data-mask": "cpf",
                    "inputmode": "numeric",
                    "maxlength": "14",
                }
            ),
            "cep": forms.TextInput(
                attrs={
                    "placeholder": "00000-000",
                    "data-mask": "cep",
                    "inputmode": "numeric",
                    "maxlength": "9",
                }
            ),
            "endereco": forms.TextInput(attrs={"placeholder": "Rua, avenida..."}),
            "numero": forms.TextInput(attrs={"placeholder": "Numero"}),
            "complemento": forms.TextInput(attrs={"placeholder": "Apto, bloco, referencia..."}),
            "bairro": forms.TextInput(attrs={"placeholder": "Bairro"}),
            "cidade": forms.TextInput(attrs={"placeholder": "Cidade"}),
            "estado": forms.TextInput(attrs={"placeholder": "UF", "maxlength": "2"}),
            "observacoes": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Adicione observacoes ou notas sobre o cliente...",
                }
            ),
            "data_nascimento": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
        }
        labels = {
            "cep": "CEP",
            "endereco": "Rua / Logradouro",
            "numero": "Numero",
            "complemento": "Complemento",
            "bairro": "Bairro",
            "cidade": "Cidade",
            "estado": "UF",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_masked_cpf_field(self.fields["cpf"])
        for field_name in (
            "cpf",
            "telefone",
            "data_nascimento",
            "cep",
            "endereco",
            "numero",
            "complemento",
            "bairro",
            "cidade",
            "estado",
            "observacoes",
            "programas_concierge",
            "razao_social",
            "cnpj",
        ):
            self.fields[field_name].required = False
        self.fields["ativo"].initial = True
        self.fields["tipo_cliente"].label = "Tipo de cliente"

    def clean_data_nascimento(self):
        return parse_br_date(self.cleaned_data.get("data_nascimento"), field_label="Data de nascimento")

    def clean_cep(self):
        return _format_cep(self.cleaned_data.get("cep"))

    def clean_estado(self):
        return _format_uf(self.cleaned_data.get("estado"))

    def clean_cpf(self):
        cpf = self.cleaned_data.get("cpf")
        if not cpf:
            return _generate_internal_cpf()
        cpf = validate_cpf_digits(cpf)
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Ja existe um cliente com este CPF.")
        return cpf

    def clean(self):
        cleaned = super().clean()
        full_name = " ".join(str(cleaned.get("full_name") or self.data.get("full_name") or "").split())
        first_name = " ".join(str(cleaned.get("first_name") or "").split())
        last_name = " ".join(str(cleaned.get("last_name") or "").split())
        full_first_name, full_last_name = _split_full_name(full_name)

        if full_name:
            first_name = first_name or full_first_name
            last_name = last_name or full_last_name

        if not first_name:
            self.add_error("full_name", "Informe o nome do cliente.")

        cleaned["full_name"] = " ".join([first_name, last_name]).strip()
        cleaned["first_name"] = first_name
        cleaned["last_name"] = last_name

        password = cleaned.get("password")
        confirm_password = cleaned.get("confirm_password")
        if password or confirm_password:
            if password != confirm_password:
                self.add_error("confirm_password", "As senhas nao coincidem.")
        return cleaned


class AeroportoForm(forms.ModelForm):
    class Meta:
        model = Aeroporto
        fields = ['sigla', 'nome']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sigla"].widget.attrs.update({
            "placeholder": "Ex: GRU",
            "autocomplete": "off",
            "maxlength": "10",
        })
        self.fields["nome"].widget.attrs.update({
            "placeholder": "Ex: Sao Paulo (Guarulhos)",
            "autocomplete": "off",
        })


class EmissaoPassagemForm(forms.ModelForm):
    tipo_emissao = forms.ChoiceField(
        choices=(
            ("cliente", "Conta propria da agencia"),
            ("administrada", "Conta administrada"),
            ("parceiro", "Emissor parceiro"),
            ("concierge", "Pontos do cliente concierge"),
        ),
        initial="cliente",
    )
    modelo_operacional = forms.ChoiceField(
        choices=(
            ("", "Automatico"),
            ("1", "Modelo 1 - Venda direta"),
            ("2", "Modelo 2 - Intermediario"),
        ),
        required=False,
        initial="",
    )
    conta_administrada = forms.ModelChoiceField(
        queryset=ContaAdministrada.objects.none(), required=False
    )
    hotel_vinculado = forms.ModelChoiceField(
        queryset=EmissaoHotel.objects.none(), required=False
    )
    criar_hotel_nome = forms.CharField(required=False)
    criar_hotel_check_in = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    criar_hotel_check_out = forms.DateField(required=False, input_formats=["%Y-%m-%d"])
    duracao_voo_ida_minutos = forms.CharField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "step": "60"}),
    )
    fuso_horario_ida = forms.TypedChoiceField(
        choices=[("", "+0h")] + TIMEZONE_OFFSET_CHOICES,
        coerce=int,
        required=False,
        empty_value=0,
        initial=0,
    )
    duracao_voo_volta_minutos = forms.CharField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "step": "60"}),
    )
    fuso_horario_volta = forms.TypedChoiceField(
        choices=[("", "+0h")] + TIMEZONE_OFFSET_CHOICES,
        coerce=int,
        required=False,
        empty_value=0,
        initial=0,
    )

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        _dt_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        self.fields['data_ida'].input_formats = _dt_formats
        self.fields['data_volta'].input_formats = _dt_formats
        for f in [
            'qtd_adultos',
            'qtd_criancas',
            'qtd_bebes',
            'duracao_voo_ida_minutos',
            'fuso_horario_ida',
            'duracao_voo_volta_minutos',
            'fuso_horario_volta',
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
        self.fields["bagagem_mao"].required = False
        self.fields["bagagem_despachada"].required = False
        self.fields["valor_referencia"].required = False
        if "tipo_operacao" in self.fields:
            self.fields["tipo_operacao"].required = False
            self.fields["tipo_operacao"].widget = forms.HiddenInput()
        if "valor_taxas" in self.fields:
            self.fields["valor_taxas"].required = False
        if "valor_total_final" in self.fields:
            self.fields["valor_total_final"].required = False
        self.fields["bagagem_mao"].choices = [
            ("", "Sob consulta"),
            *self.fields["bagagem_mao"].choices,
        ]
        self.fields["bagagem_despachada"].choices = [
            ("", "Sob consulta"),
            *self.fields["bagagem_despachada"].choices,
        ]
        hoteis_qs = EmissaoHotel.objects.select_related("cliente")
        if empresa:
            hoteis_qs = hoteis_qs.filter(cliente__empresa=empresa)
        self.fields["hotel_vinculado"].queryset = hoteis_qs.order_by("-check_in")

        self.initial["duracao_voo_ida_minutos"] = _format_duration_from_minutes(
            getattr(self.instance, "duracao_voo_ida_minutos", 0) or 0
        )
        self.initial["duracao_voo_volta_minutos"] = _format_duration_from_minutes(
            getattr(self.instance, "duracao_voo_volta_minutos", 0) or 0
        )
        self.fields["duracao_voo_ida_minutos"].widget.attrs.update({"placeholder": "Ex: 05:30"})
        self.fields["duracao_voo_volta_minutos"].widget.attrs.update({"placeholder": "Ex: 04:45"})

        selected_tipo = self.data.get("tipo_emissao")
        if not selected_tipo:
            selected_tipo = self.initial.get("tipo_emissao")
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
            titular_id = (
                self.data.get("conta_administrada")
                or self.initial.get("conta_administrada")
                or getattr(self.instance, "conta_administrada_id", None)
            )
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__conta_administrada_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()
        elif selected_tipo == "parceiro":
            programas_qs = ProgramaFidelidade.objects.all()
        else:
            titular_id = (
                self.data.get("cliente")
                or self.initial.get("cliente")
                or getattr(self.instance, "cliente_id", None)
            )
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
        if tipo == "concierge":
            tipo_cli = getattr(cliente, "tipo_cliente", "") if cliente else ""
            if tipo_cli != Cliente.TIPO_CONCIERGE:
                raise forms.ValidationError(
                    "Pontos do cliente concierge so podem ser usados quando o cliente e do tipo Concierge."
                )
        modelo_escolhido = (cleaned.get("modelo_operacional") or "").strip()
        tipo_cli = getattr(cliente, "tipo_cliente", "") if cliente else ""
        if tipo == "concierge":
            cleaned["tipo_operacao"] = EmissaoPassagem.TIPO_CONCIERGE
        elif tipo == "parceiro":
            cleaned["tipo_operacao"] = EmissaoPassagem.TIPO_EMISSOR_PARCEIRO
        elif tipo_cli == Cliente.TIPO_INTERMEDIARIO or modelo_escolhido == "2":
            cleaned["tipo_operacao"] = EmissaoPassagem.TIPO_INTERMEDIARIO
        else:
            cleaned["tipo_operacao"] = EmissaoPassagem.TIPO_VENDA_DIRETA
        criar_nome = (cleaned.get("criar_hotel_nome") or "").strip()
        hotel_vinculado = cleaned.get("hotel_vinculado")
        if criar_nome and hotel_vinculado:
            raise forms.ValidationError("Escolha um hotel existente ou crie um novo, não ambos.")
        cleaned["duracao_voo_ida_minutos"] = _parse_duration_to_minutes(cleaned.get("duracao_voo_ida_minutos"))
        cleaned["duracao_voo_volta_minutos"] = _parse_duration_to_minutes(cleaned.get("duracao_voo_volta_minutos"))
        cleaned["fuso_horario_ida"] = int(cleaned.get("fuso_horario_ida") or 0)
        cleaned["fuso_horario_volta"] = int(cleaned.get("fuso_horario_volta") or 0)
        return cleaned

    class Meta:
        model = EmissaoPassagem
        fields = [
            'tipo_emissao',
            'modelo_operacional',
            'tipo_operacao',
            'cliente',
            'conta_administrada',
            'programa',
            'emissor_parceiro',
            'aeroporto_partida',
            'aeroporto_destino',
            'data_ida',
            'data_volta',
            'duracao_voo_ida_minutos',
            'fuso_horario_ida',
            'duracao_voo_volta_minutos',
            'fuso_horario_volta',
            'bagagem_mao',
            'bagagem_despachada',
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
            'valor_total_final',
            'custo_emissor',
            'valor_cobrado_cliente',
            'milhas_do_cliente',
            'lucro',
            'hotel_vinculado',
            'comprovante_pagamento',
        ]
        widgets = {
            'data_ida': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'data_volta': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'valor_referencia_pontos': forms.NumberInput(attrs={'step': '0.01', 'readonly': 'readonly'}),
            'valor_milheiro_parceiro': forms.NumberInput(attrs={'step': '0.01'}),
            'valor_venda_final': forms.NumberInput(attrs={'step': '0.01'}),
            'valor_total_final': forms.NumberInput(attrs={'step': '0.01'}),
            'custo_emissor': forms.NumberInput(attrs={'step': '0.01'}),
            'valor_cobrado_cliente': forms.NumberInput(attrs={'step': '0.01'}),
            'lucro': forms.NumberInput(attrs={'step': '0.01', 'readonly': 'readonly'}),
            'criar_hotel_check_in': forms.DateInput(attrs={'type': 'date'}),
            'criar_hotel_check_out': forms.DateInput(attrs={'type': 'date'}),
        }
        



class PassageiroFrequenteForm(forms.ModelForm):
    class Meta:
        model = PassageiroFrequente
        fields = [
            "nome",
            "tipo",
            "cpf",
            "rg",
            "passaporte",
            "passaporte_validade",
            "data_nascimento",
            "relacao",
        ]
        widgets = {
            "cpf": forms.TextInput(
                attrs={
                    "placeholder": "000.000.000-00",
                    "data-mask": "cpf",
                    "inputmode": "numeric",
                    "maxlength": "14",
                }
            ),
            "data_nascimento": forms.TextInput(
                attrs={
                    "placeholder": "DD/MM/AAAA",
                    "data-mask": "date",
                    "inputmode": "numeric",
                    "maxlength": "10",
                }
            ),
            "passaporte_validade": forms.DateInput(attrs={"type": "date"}),
            "relacao": forms.TextInput(attrs={"placeholder": "Ex.: Filho, Cônjuge, Sócio"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _configure_masked_cpf_field(self.fields["cpf"])

    def clean_cpf(self):
        return validate_cpf_digits(self.cleaned_data.get("cpf"), field_label="CPF do passageiro")

    def clean_data_nascimento(self):
        return parse_br_date(self.cleaned_data.get("data_nascimento"), field_label="Data de nascimento")

    def clean(self):
        cleaned = super().clean()
        passaporte = (cleaned.get("passaporte") or "").strip()
        if passaporte and not cleaned.get("passaporte_validade"):
            self.add_error("passaporte_validade", "Informe a validade do passaporte.")
        return cleaned


class InteresseViagemClienteForm(forms.ModelForm):
    continente = forms.ChoiceField(required=False, choices=[])
    pais = forms.ChoiceField(required=False, choices=[])
    cidade_destino = forms.ChoiceField(required=False, choices=[])
    origem = forms.ChoiceField(required=False, choices=[])
    destino = forms.ChoiceField(required=False, choices=[])
    programa_fidelidade = forms.ChoiceField(required=False, choices=[])
    companhia_aerea = forms.ChoiceField(required=False, choices=[])
    meses_ida = forms.ChoiceField(required=False, choices=[], label="Mês de ida")
    meses_volta = forms.ChoiceField(required=False, choices=[], label="Mês de volta")
    dias_ida = forms.ChoiceField(required=False, choices=[], label="Dia de ida")
    dias_volta = forms.ChoiceField(required=False, choices=[], label="Dia de volta")
    semestres_ida = forms.ChoiceField(required=False, choices=[], label="Semestre de ida")
    semestres_volta = forms.ChoiceField(required=False, choices=[], label="Semestre de volta")

    class Meta:
        model = InteresseViagemCliente
        fields = [
            "nome",
            "continente",
            "pais",
            "cidade_destino",
            "origem",
            "destino",
            "classe",
            "programa_fidelidade",
            "companhia_aerea",
            "meses_ida",
            "meses_volta",
            "dias_ida",
            "dias_volta",
            "semestres_ida",
            "semestres_volta",
            "ativo",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"placeholder": "Ex.: Europa em setembro"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        continent_choices = [("", "Qualquer continente"), *AlertaViagem.CONTINENTE_CHOICES]
        self.fields["continente"].choices = continent_choices
        self.fields["classe"].choices = [("", "Qualquer classe"), *InteresseViagemCliente.CLASSE_CHOICES[1:]]
        self.fields["meses_ida"].choices = [("", "Qualquer mês"), *MONTH_CHOICES]
        self.fields["meses_volta"].choices = [("", "Qualquer mês"), *MONTH_CHOICES]
        self.fields["dias_ida"].choices = [("", "Qualquer dia"), *DAY_CHOICES]
        self.fields["dias_volta"].choices = [("", "Qualquer dia"), *DAY_CHOICES]
        self.fields["semestres_ida"].choices = [("", "Qualquer semestre"), *SEMESTER_CHOICES]
        self.fields["semestres_volta"].choices = [("", "Qualquer semestre"), *SEMESTER_CHOICES]

        airport_choices = []
        seen_airports = set()
        country_choices = []
        seen_countries = set()
        city_choices = []
        seen_cities = set()

        for airport in Aeroporto.objects.all().order_by("sigla", "nome"):
            code = (airport.sigla or "").strip().upper()
            if code and code not in seen_airports:
                label_city = airport.cidade or airport.nome
                airport_choices.append((code, f"{code} • {label_city}"))
                seen_airports.add(code)

            resolved = infer_airport_location(airport)
            country = (resolved.get("pais") or "").strip()
            city = (resolved.get("cidade") or airport.cidade or "").strip()
            if country and country not in seen_countries:
                country_choices.append((country, country))
                seen_countries.add(country)
            if city and city not in seen_cities:
                city_choices.append((city, city))
                seen_cities.add(city)

        def _append_current_choice(field_name, choices, default_label):
            current_value = (self.initial.get(field_name) or getattr(self.instance, field_name, "") or "").strip()
            if current_value and all(value != current_value for value, _ in choices):
                choices.append((current_value, current_value))
            self.fields[field_name].choices = [("", default_label), *choices]

        _append_current_choice("pais", sorted(country_choices, key=lambda item: item[1]), "Qualquer país")
        _append_current_choice("cidade_destino", sorted(city_choices, key=lambda item: item[1]), "Qualquer cidade")
        _append_current_choice("origem", airport_choices, "Qualquer origem")
        _append_current_choice("destino", airport_choices, "Qualquer destino")

        program_choices = [
            (nome, nome)
            for nome in ProgramaFidelidade.objects.order_by("nome").values_list("nome", flat=True).distinct()
            if nome
        ]
        company_choices = [
            (nome, nome)
            for nome in CompanhiaAerea.objects.order_by("nome").values_list("nome", flat=True).distinct()
            if nome
        ]
        _append_current_choice(
            "programa_fidelidade",
            program_choices,
            "Qualquer programa",
        )
        _append_current_choice(
            "companhia_aerea",
            company_choices,
            "Qualquer companhia",
        )

        self.fields["meses_ida"].initial = str((self.instance.meses_ida or [None])[0] or "")
        self.fields["meses_volta"].initial = str((self.instance.meses_volta or [None])[0] or "")
        self.fields["dias_ida"].initial = str((self.instance.dias_ida or [None])[0] or "")
        self.fields["dias_volta"].initial = str((self.instance.dias_volta or [None])[0] or "")
        self.fields["semestres_ida"].initial = str((self.instance.semestres_ida or [None])[0] or "")
        self.fields["semestres_volta"].initial = str((self.instance.semestres_volta or [None])[0] or "")

    def clean_meses_ida(self):
        value = self.cleaned_data.get("meses_ida")
        return [int(value)] if value else []

    def clean_meses_volta(self):
        value = self.cleaned_data.get("meses_volta")
        return [int(value)] if value else []

    def clean_dias_ida(self):
        value = self.cleaned_data.get("dias_ida")
        return [int(value)] if value else []

    def clean_dias_volta(self):
        value = self.cleaned_data.get("dias_volta")
        return [int(value)] if value else []

    def clean_semestres_ida(self):
        value = self.cleaned_data.get("semestres_ida")
        return [int(value)] if value else []

    def clean_semestres_volta(self):
        value = self.cleaned_data.get("semestres_volta")
        return [int(value)] if value else []


class EmissaoHotelForm(forms.ModelForm):
    class Meta:
        model = EmissaoHotel
        fields = [
            'cliente',
            'nome_hotel',
            'check_in',
            'check_out',
            'voo_vinculado',
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
        self.fields["cliente"].empty_label = "Selecione o cliente"
        self.fields["nome_hotel"].widget.attrs.update({
            "placeholder": "Digite o nome do hotel",
            "autocomplete": "off",
        })
        self.fields["check_in"].widget.attrs.update({
            "placeholder": "dd/mm/aaaa",
        })
        self.fields["check_out"].widget.attrs.update({
            "placeholder": "dd/mm/aaaa",
        })
        # Voo vinculado — começa vazio, preenchido via JS ao selecionar cliente
        self.fields["voo_vinculado"].required = False
        self.fields["voo_vinculado"].empty_label = "Selecione o cliente primeiro"
        if self.instance and self.instance.pk and self.instance.cliente_id:
            self.fields["voo_vinculado"].queryset = CotacaoVoo.objects.filter(
                cliente_id=self.instance.cliente_id
            ).select_related("origem", "destino", "programa")
        else:
            self.fields["voo_vinculado"].queryset = CotacaoVoo.objects.none()
        self.fields["valor_referencia"].widget.attrs.update({
            "placeholder": "0.00",
            "step": "0.01",
            "min": "0",
        })
        self.fields["valor_pago"].widget.attrs.update({
            "placeholder": "0.00",
            "step": "0.01",
            "min": "0",
        })
        self.fields["economia_obtida"].required = False
        self.fields["economia_obtida"].widget.attrs.update({
            "placeholder": "0.00",
            "step": "0.01",
            "min": "0",
            "readonly": "readonly",
        })


class EmissorParceiroForm(forms.ModelForm):
    class Meta:
        model = EmissorParceiro
        fields = ["nome", "telefone", "usuario", "programas", "ativo", "observacoes"]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 5}),
        }

    def __init__(self, *args, **kwargs):
        empresa = kwargs.pop("empresa", None)
        super().__init__(*args, **kwargs)
        self.fields["programas"].required = False
        self.fields["nome"].widget.attrs.update({
            "placeholder": "Ex: Emissor Premium",
            "autocomplete": "off",
        })
        self.fields["telefone"].widget.attrs.update({
            "placeholder": "Ex: (11) 99999-9999",
            "autocomplete": "off",
        })
        self.fields["usuario"].empty_label = "Selecione o usuario"
        self.fields["observacoes"].widget.attrs.update({
            "placeholder": "Digite observacoes, notas ou informacoes relevantes sobre este emissor...",
        })
        if empresa:
            programas_qs = ProgramaFidelidade.objects.filter(
                Q(contafidelidade__cliente__empresa=empresa)
                | Q(contafidelidade__conta_administrada__empresa=empresa)
            ).distinct()
        else:
            programas_qs = ProgramaFidelidade.objects.all()
        self.fields["programas"].queryset = programas_qs


class CotacaoVooForm(forms.ModelForm):
    CLASSE_CHOICES = (
        ("", "Selecione a classe"),
        ("Economica", "Econômica"),
        ("Premium Economy", "Premium Economy"),
        ("Executiva", "Executiva"),
        ("Primeira Classe", "Primeira Classe"),
    )

    companhia_aerea = forms.ChoiceField(choices=[], required=False)
    classe = forms.ChoiceField(choices=CLASSE_CHOICES, required=False)
    duracao_voo_ida_minutos = forms.CharField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "step": "60"}),
    )
    fuso_horario_ida = forms.TypedChoiceField(
        choices=TIMEZONE_OFFSET_CHOICES,
        coerce=int,
        required=False,
        empty_value=0,
        initial=0,
    )
    duracao_voo_volta_minutos = forms.CharField(
        required=False,
        widget=forms.TimeInput(attrs={"type": "time", "step": "60"}),
    )
    fuso_horario_volta = forms.TypedChoiceField(
        choices=TIMEZONE_OFFSET_CHOICES,
        coerce=int,
        required=False,
        empty_value=0,
        initial=0,
    )
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
        _dt_formats = ['%Y-%m-%dT%H:%M', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M']
        self.fields['data_ida'].input_formats = _dt_formats
        self.fields['data_volta'].input_formats = _dt_formats
        self.fields['companhia_aerea'].choices = [
            ("", "Selecione a companhia")
        ] + [(c.nome, c.nome) for c in CompanhiaAerea.objects.all()]
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
        self.fields["cliente"].empty_label = "Selecione o cliente"
        self.fields["conta_administrada"].empty_label = "Selecione a conta"
        self.fields["origem"].empty_label = "Selecione o aeroporto de origem"
        self.fields["destino"].empty_label = "Selecione o aeroporto de destino"
        self.fields["programa"].required = False
        self.initial["duracao_voo_ida_minutos"] = _format_duration_from_minutes(
            getattr(self.instance, "duracao_voo_ida_minutos", 0)
        )
        self.initial["duracao_voo_volta_minutos"] = _format_duration_from_minutes(
            getattr(self.instance, "duracao_voo_volta_minutos", 0)
        )

        selected_tipo = self.data.get("tipo_titular") or self.initial.get("tipo_titular") or ("administrada" if getattr(self.instance, "conta_administrada_id", None) else "cliente")
        self.initial.setdefault("tipo_titular", selected_tipo)
        self.fields["cliente"].required = True
        self.fields["conta_administrada"].required = selected_tipo == "administrada"

        titular_id = None
        if selected_tipo == "administrada":
            titular_id = (
                self.data.get("conta_administrada")
                or self.initial.get("conta_administrada")
                or getattr(self.instance, "conta_administrada_id", None)
            )
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__conta_administrada_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()
        else:
            titular_id = (
                self.data.get("cliente")
                or self.initial.get("cliente")
                or getattr(self.instance, "cliente_id", None)
            )
            programas_qs = ProgramaFidelidade.objects.filter(
                contafidelidade__cliente_id=titular_id
            ) if titular_id else ProgramaFidelidade.objects.none()

        if self.instance and self.instance.programa_id and not programas_qs.filter(id=self.instance.programa_id).exists():
            programas_qs = programas_qs | ProgramaFidelidade.objects.filter(id=self.instance.programa_id)
        self.fields["programa"].queryset = programas_qs.distinct()
        self.fields["programa"].empty_label = "Selecione o programa"
        self.fields["duracao_voo_ida_minutos"].widget.attrs.update({"placeholder": "Ex: 05:30"})
        self.fields["duracao_voo_volta_minutos"].widget.attrs.update({"placeholder": "Ex: 04:45"})

        self.fields["companhia_aerea"].widget.attrs.update({"data-role": "companhia-select"})
        self.fields["data_ida"].widget.attrs.update({"placeholder": "Selecione data e horário"})
        self.fields["data_volta"].widget.attrs.update({"placeholder": "Selecione data e horário"})
        self.fields["qtd_passageiros"].widget.attrs.update({"min": "1", "placeholder": "Ex: 2"})
        self.fields["valor_passagem"].widget.attrs.update({"step": "0.01", "placeholder": "Ex: 2500.00"})
        self.fields["taxas"].widget.attrs.update({"step": "0.01", "placeholder": "Ex: 150.00"})
        self.fields["milhas"].widget.attrs.update({"placeholder": "Ex: 20000"})
        self.fields["valor_milheiro"].widget.attrs.update({"step": "0.01", "placeholder": "Ex: 35.00"})
        self.fields["parcelas"].widget.attrs.update({"min": "1"})
        self.fields["juros"].widget.attrs.update({"step": "0.01"})
        self.fields["desconto"].widget.attrs.update({"step": "0.01"})
        self.fields["mostrar_valor_parcelado"].required = False
        self.fields["observacoes"].widget.attrs.update({
            "rows": 4,
            "placeholder": "Observações comerciais ou regras do resgate",
        })

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
        cleaned["duracao_voo_ida_minutos"] = _parse_duration_to_minutes(cleaned.get("duracao_voo_ida_minutos"))
        cleaned["duracao_voo_volta_minutos"] = _parse_duration_to_minutes(cleaned.get("duracao_voo_volta_minutos"))
        cleaned["fuso_horario_ida"] = int(cleaned.get("fuso_horario_ida") or 0)
        cleaned["fuso_horario_volta"] = int(cleaned.get("fuso_horario_volta") or 0)
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
            'duracao_voo_ida_minutos',
            'fuso_horario_ida',
            'duracao_voo_volta_minutos',
            'fuso_horario_volta',
            'qtd_passageiros',
            'classe',
            'observacoes',
            'valor_passagem',
            'valor_referencia_manual',
            'taxas',
            'milhas',
            'valor_milheiro',
            'parcelas',
            'juros',
            'desconto',
            'mostrar_valor_parcelado',
            'validade',
            'status',
        ]
        labels = {
            'parcelas': 'Número de parcelas sem juros',
            'valor_referencia_manual': 'Valor de referência manual (R$)',
        }
        widgets = {
            'data_ida': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'data_volta': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'validade': forms.DateInput(attrs={'type': 'date'}),
            'valor_referencia_manual': forms.NumberInput(attrs={'step': '0.01', 'placeholder': 'Ex: 2500.00'}),
        }


class CalculadoraCotacaoForm(forms.Form):
    valor_passagem = forms.DecimalField(max_digits=10, decimal_places=2)
    taxas = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
    milhas = forms.DecimalField(max_digits=12, decimal_places=2, required=False, initial=0)
    valor_milheiro = forms.DecimalField(max_digits=10, decimal_places=2, required=False, initial=0)
    parcelas = forms.IntegerField(required=False, initial=1)
    juros = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=1)
    desconto = forms.DecimalField(max_digits=5, decimal_places=2, required=False, initial=1)


class AlertaViagemForm(forms.ModelForm):
    alerta_bruto = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 10,
                "placeholder": "Cole aqui o alerta bruto recebido do Telegram.",
            }
        ),
        label="Alerta bruto",
    )
    conteudo = forms.CharField(
        required=False,
        widget=forms.Textarea(
            attrs={
                "rows": 6,
                "placeholder": "Texto completo do alerta (pode incluir emojis, links e listas).",
                "style": "resize:vertical;",
            }
        ),
    )
    datas_ida = forms.JSONField(required=False, widget=forms.HiddenInput)
    datas_volta = forms.JSONField(required=False, widget=forms.HiddenInput)

    class Meta:
        model = AlertaViagem
        fields = [
            "titulo",
            "conteudo",
            "continente",
            "pais",
            "cidade_destino",
            "origem",
            "destino",
            "classe",
            "programa_fidelidade",
            "companhia_aerea",
            "valor_milhas",
            "valor_reais",
            "datas_ida",
            "datas_volta",
            "manter_apos_cinco_dias",
            "ocultar_apos_datas",
            "ativo",
        ]
        widgets = {}
        labels = {
            "cidade_destino": "Cidade destino",
            "programa_fidelidade": "Programa de fidelidade",
            "companhia_aerea": "Companhia aérea",
            "valor_milhas": "Valor em milhas",
            "valor_reais": "Valor em reais",
            "datas_ida": "Datas de ida",
            "datas_volta": "Datas de volta",
            "manter_apos_cinco_dias": "Continuar após 5 dias",
            "ocultar_apos_datas": "Ocultar quando todas as datas passarem",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["valor_milhas"].required = False
        self.fields["valor_reais"].required = False
        self.fields["manter_apos_cinco_dias"].required = False
        self.fields["ocultar_apos_datas"].required = False

    def _clean_datas(self, field_name):
        raw_value = self.cleaned_data.get(field_name) or []
        if raw_value is None:
            return []
        if not isinstance(raw_value, list):
            raise forms.ValidationError("Selecione ao menos uma data válida.")
        datas = []
        for item in raw_value:
            if not isinstance(item, str):
                raise forms.ValidationError("Selecione datas válidas.")
            try:
                from datetime import date

                date.fromisoformat(item)
            except ValueError as exc:
                raise forms.ValidationError("Selecione datas válidas.") from exc
            datas.append(item)
        return datas

    def clean_datas_ida(self):
        return self._clean_datas("datas_ida")

    def clean_datas_volta(self):
        return self._clean_datas("datas_volta")

    def clean_valor_milhas(self):
        value = self.cleaned_data.get("valor_milhas")
        if value in (None, "") or int(value or 0) <= 0:
            raise forms.ValidationError("Informe a quantidade de milhas do alerta.")
        return value

class CompanhiaAereaForm(forms.ModelForm):
    class Meta:
        model = CompanhiaAerea
        fields = ["nome", "site_url"]
        widgets = {
            "nome": forms.TextInput(),
            "site_url": forms.URLInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].widget.attrs.update({
            "placeholder": "Ex: LATAM Airlines",
            "autocomplete": "off",
        })
        self.fields["site_url"].widget.attrs.update({
            "placeholder": "https://www.latam.com/pt_br/minhas-viagens",
            "autocomplete": "off",
        })


class EmpresaForm(forms.ModelForm):
    admin_nome = forms.CharField(max_length=150, label="Nome do admin")
    admin_cpf = forms.CharField(max_length=14, label="CPF do admin")
    admin_email = forms.EmailField(required=False, label="Email do admin")
    admin_password = forms.CharField(
        widget=forms.PasswordInput, label="Senha inicial do admin"
    )
    remover_logo_documentos = forms.BooleanField(required=False)

    class Meta:
        model = Empresa
        fields = [
            "nome",
            "responsavel_nome",
            "email_contato",
            "telefone_contato",
            "whatsapp",
            "website",
            "cidade",
            "estado",
            "endereco",
            "descricao_rodape",
            "logo_documentos",
            "ocultar_logo_documentos",
            "limite_colaboradores",
            "ativo",
        ]
        labels = {
            "nome": "Nome da empresa",
            "responsavel_nome": "Responsavel pelo atendimento",
            "email_contato": "E-mail principal",
            "telefone_contato": "Telefone principal",
            "whatsapp": "WhatsApp",
            "website": "Website",
            "cidade": "Cidade",
            "estado": "Estado",
            "endereco": "Endereco",
            "descricao_rodape": "Mensagem institucional",
            "logo_documentos": "Logo nos documentos",
            "ocultar_logo_documentos": "Nao exibir logo principal nos documentos",
            "limite_colaboradores": "Limite de colaboradores",
            "ativo": "Empresa ativa",
        }
        widgets = {
            "nome": forms.TextInput(
                attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2"}
            ),
            "responsavel_nome": forms.TextInput(),
            "email_contato": forms.EmailInput(),
            "telefone_contato": forms.TextInput(),
            "whatsapp": forms.TextInput(),
            "website": forms.URLInput(),
            "cidade": forms.TextInput(),
            "estado": forms.TextInput(),
            "endereco": forms.TextInput(),
            "descricao_rodape": forms.Textarea(attrs={"rows": 3}),
            "logo_documentos": forms.FileInput(
                attrs={
                    "accept": ".png,image/png",
                }
            ),
            "limite_colaboradores": forms.NumberInput(
                attrs={"class": "w-full bg-zinc-900 border border-zinc-600 text-white rounded p-2", "min": 0}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "nome": "Nome da empresa",
            "responsavel_nome": "Responsavel principal pela empresa",
            "email_contato": "contato@empresa.com",
            "telefone_contato": "(11) 99999-9999",
            "whatsapp": "(11) 99999-9999",
            "website": "https://www.empresa.com.br",
            "cidade": "Cidade base da operacao",
            "estado": "Estado",
            "endereco": "Rua, numero e complemento",
            "descricao_rodape": "Texto institucional para PDFs e visualizacoes.",
            "logo_documentos": "",
            "limite_colaboradores": "Ex: 10",
            "admin_nome": "Nome completo do administrador",
            "admin_cpf": "000.000.000-00",
            "admin_email": "email@empresa.com",
            "admin_password": "Senha inicial",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.pop("class", None)
            field.widget.attrs["autocomplete"] = "off"
            if field_name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[field_name]
        self.fields["limite_colaboradores"].widget.attrs["min"] = 0
        self.fields["ativo"].widget.attrs["class"] = "superadmin-form__checkbox"
        self.fields["ocultar_logo_documentos"].widget.attrs["class"] = "superadmin-form__checkbox"
        self.fields["logo_documentos"].widget.attrs["class"] = "company-brand-form__file-input"

    def clean_logo_documentos(self):
        logo = self.cleaned_data.get("logo_documentos")
        if not logo:
            return logo

        if getattr(logo, "size", 0) > 150 * 1024:
            raise forms.ValidationError("Envie uma logo com no maximo 150KB.")

        content_type = getattr(logo, "content_type", "")
        if content_type and content_type != "image/png":
            raise forms.ValidationError("Envie a logo em PNG com fundo transparente.")

        return logo

    def clean_admin_cpf(self):
        cpf = validate_cpf_digits(self.cleaned_data.get("admin_cpf"), field_label="CPF do admin")
        if Cliente.objects.filter(cpf=cpf).exists():
            raise forms.ValidationError("Já existe um cliente com este CPF.")
        return cpf

    def save(self, *, criado_por):
        data = self.cleaned_data
        with transaction.atomic():
            empresa = super().save(commit=False)
            empresa.responsavel_nome = data.get("responsavel_nome") or data["admin_nome"]
            empresa.email_contato = data.get("email_contato") or data.get("admin_email", "")
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


class EmpresaProfileForm(forms.ModelForm):
    remover_logo_documentos = forms.BooleanField(required=False)

    class Meta:
        model = Empresa
        fields = [
            "nome",
            "responsavel_nome",
            "email_contato",
            "telefone_contato",
            "whatsapp",
            "website",
            "cidade",
            "estado",
            "endereco",
            "descricao_rodape",
            "logo_documentos",
            "ocultar_logo_documentos",
        ]
        labels = {
            "nome": "Nome da empresa",
            "responsavel_nome": "Responsavel pelo atendimento",
            "email_contato": "E-mail principal",
            "telefone_contato": "Telefone principal",
            "whatsapp": "WhatsApp",
            "website": "Website",
            "cidade": "Cidade",
            "estado": "Estado",
            "endereco": "Endereco",
            "descricao_rodape": "Mensagem institucional",
            "logo_documentos": "Logo nos documentos",
            "ocultar_logo_documentos": "Nao exibir logo principal nos documentos",
        }
        widgets = {
            "nome": forms.TextInput(),
            "responsavel_nome": forms.TextInput(),
            "email_contato": forms.EmailInput(),
            "telefone_contato": forms.TextInput(),
            "whatsapp": forms.TextInput(),
            "website": forms.URLInput(),
            "cidade": forms.TextInput(),
            "estado": forms.TextInput(),
            "endereco": forms.TextInput(),
            "descricao_rodape": forms.Textarea(attrs={"rows": 4}),
            "logo_documentos": forms.FileInput(
                attrs={
                    "accept": ".png,image/png",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "nome": "Nome de exibicao da empresa",
            "responsavel_nome": "Responsavel principal pelo atendimento",
            "email_contato": "contato@empresa.com",
            "telefone_contato": "(11) 99999-9999",
            "whatsapp": "(11) 99999-9999",
            "website": "https://www.empresa.com.br",
            "cidade": "Cidade base da operacao",
            "estado": "Estado",
            "endereco": "Rua, numero e complemento",
            "descricao_rodape": "Texto institucional usado nas visualizacoes e PDFs.",
            "logo_documentos": "",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.pop("class", None)
            field.widget.attrs["autocomplete"] = "off"
            if field_name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[field_name]
        self.fields["ocultar_logo_documentos"].widget.attrs["class"] = "superadmin-form__checkbox"
        self.fields["logo_documentos"].widget.attrs["class"] = "company-brand-form__file-input"

    def clean_logo_documentos(self):
        logo = self.cleaned_data.get("logo_documentos")
        if not logo:
            return logo

        if getattr(logo, "size", 0) > 150 * 1024:
            raise forms.ValidationError("Envie uma logo com no maximo 150KB.")

        content_type = getattr(logo, "content_type", "")
        if content_type and content_type != "image/png":
            raise forms.ValidationError("Envie a logo em PNG com fundo transparente.")

        return logo

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded_logo = self.files.get("logo_documentos")
        if self.cleaned_data.get("remover_logo_documentos") and not uploaded_logo and instance.logo_documentos:
            instance.logo_documentos.delete(save=False)
            instance.logo_documentos = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class EmpresaDocumentTextsForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            "cotacao_observacao_padrao",
            "cotacao_condicoes_gerais",
            "cotacao_hint_valor_referencia",
            "cotacao_hint_valor_encontrado",
            "cotacao_hint_taxa_embarque",
            "cotacao_hint_valor_total",
            "cotacao_hint_valor_parcelado",
            "cotacao_hint_economia",
            "emissao_observacao_confirmada",
            "emissao_observacao_pendente",
            "emissao_orientacoes",
            "emissao_cta_companhia",
            "emissao_bagagem_mao_hint",
            "emissao_bagagem_despachada_hint",
            "emissao_hint_taxa_embarque",
            "emissao_hint_taxa_servico",
            "emissao_hint_valor_total",
        ]
        labels = {
            "cotacao_observacao_padrao": "Observacao importante padrao",
            "cotacao_condicoes_gerais": "Condicoes gerais padrao",
            "cotacao_hint_valor_referencia": "Descricao de valor de referencia",
            "cotacao_hint_valor_encontrado": "Descricao de valor encontrado",
            "cotacao_hint_taxa_embarque": "Descricao de taxa de embarque",
            "cotacao_hint_valor_total": "Descricao de valor total",
            "cotacao_hint_valor_parcelado": "Descricao de valor parcelado",
            "cotacao_hint_economia": "Descricao de valor economizado",
            "emissao_observacao_confirmada": "Observacao padrao para emissao confirmada",
            "emissao_observacao_pendente": "Observacao padrao para emissao pendente",
            "emissao_orientacoes": "Orientacoes padrao para a viagem",
            "emissao_cta_companhia": "Texto do botao da companhia",
            "emissao_bagagem_mao_hint": "Descricao de bagagem de mao",
            "emissao_bagagem_despachada_hint": "Descricao de bagagem despachada",
            "emissao_hint_taxa_embarque": "Descricao de taxa de embarque",
            "emissao_hint_taxa_servico": "Descricao de taxa de servico",
            "emissao_hint_valor_total": "Descricao de valor total",
        }
        widgets = {
            "cotacao_observacao_padrao": forms.Textarea(attrs={"rows": 4}),
            "cotacao_condicoes_gerais": forms.Textarea(attrs={"rows": 6}),
            "emissao_observacao_confirmada": forms.Textarea(attrs={"rows": 4}),
            "emissao_observacao_pendente": forms.Textarea(attrs={"rows": 4}),
            "emissao_orientacoes": forms.Textarea(attrs={"rows": 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "cotacao_observacao_padrao": "Texto exibido em Observacoes importantes da cotacao. Se deixar vazio, o sistema usa o padrao.",
            "cotacao_condicoes_gerais": "Uma condicao por linha. Se deixar vazio, o sistema usa as regras padrao.",
            "cotacao_hint_valor_referencia": "Ex: Valor de mercado usado como comparativo.",
            "cotacao_hint_valor_encontrado": "Ex: Valor da passagem encontrada na cotacao.",
            "cotacao_hint_taxa_embarque": "Ex: Impostos e taxas aeroportuarias.",
            "cotacao_hint_valor_total": "Ex: Valor final da proposta.",
            "cotacao_hint_valor_parcelado": "Ex: Condicao de parcelamento apresentada ao cliente.",
            "cotacao_hint_economia": "Ex: Diferenca entre a referencia e a proposta.",
            "emissao_observacao_confirmada": "Texto padrao quando a emissao estiver confirmada.",
            "emissao_observacao_pendente": "Texto padrao quando a emissao ainda estiver pendente.",
            "emissao_orientacoes": "Uma orientacao por linha. Se deixar vazio, o sistema usa as orientacoes padrao.",
            "emissao_cta_companhia": "Ex: Acessar Minha Reserva",
            "emissao_bagagem_mao_hint": "Ex: Franquia definida na emissao.",
            "emissao_bagagem_despachada_hint": "Ex: Franquia validada para a tarifa emitida.",
            "emissao_hint_taxa_embarque": "Ex: Impostos e taxas aeroportuarias.",
            "emissao_hint_taxa_servico": "Ex: Consultoria e emissao.",
            "emissao_hint_valor_total": "Ex: Valor final consolidado da emissao.",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.pop("class", None)
            field.widget.attrs["autocomplete"] = "off"
            if field_name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[field_name]


class EmpresaManagementForm(forms.ModelForm):
    remover_logo_documentos = forms.BooleanField(required=False)

    class Meta:
        model = Empresa
        fields = [
            "nome",
            "responsavel_nome",
            "email_contato",
            "telefone_contato",
            "whatsapp",
            "website",
            "cidade",
            "estado",
            "endereco",
            "descricao_rodape",
            "logo_documentos",
            "ocultar_logo_documentos",
            "limite_colaboradores",
            "ativo",
        ]
        labels = {
            "nome": "Nome da empresa",
            "responsavel_nome": "Responsavel pelo atendimento",
            "email_contato": "E-mail principal",
            "telefone_contato": "Telefone principal",
            "whatsapp": "WhatsApp",
            "website": "Website",
            "cidade": "Cidade",
            "estado": "Estado",
            "endereco": "Endereco",
            "descricao_rodape": "Mensagem institucional",
            "logo_documentos": "Logo nos documentos",
            "ocultar_logo_documentos": "Nao exibir logo principal nos documentos",
            "limite_colaboradores": "Limite de colaboradores",
            "ativo": "Empresa ativa",
        }
        widgets = {
            "nome": forms.TextInput(),
            "responsavel_nome": forms.TextInput(),
            "email_contato": forms.EmailInput(),
            "telefone_contato": forms.TextInput(),
            "whatsapp": forms.TextInput(),
            "website": forms.URLInput(),
            "cidade": forms.TextInput(),
            "estado": forms.TextInput(),
            "endereco": forms.TextInput(),
            "descricao_rodape": forms.Textarea(attrs={"rows": 4}),
            "logo_documentos": forms.FileInput(
                attrs={
                    "accept": ".png,image/png",
                }
            ),
            "limite_colaboradores": forms.NumberInput(attrs={"min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "nome": "Nome da empresa",
            "responsavel_nome": "Responsavel principal pela empresa",
            "email_contato": "contato@empresa.com",
            "telefone_contato": "(11) 99999-9999",
            "whatsapp": "(11) 99999-9999",
            "website": "https://www.empresa.com.br",
            "cidade": "Cidade base da operacao",
            "estado": "Estado",
            "endereco": "Rua, numero e complemento",
            "descricao_rodape": "Texto institucional usado nas visualizacoes e PDFs.",
            "logo_documentos": "",
            "limite_colaboradores": "0 bloqueia novos operadores",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.pop("class", None)
            field.widget.attrs["autocomplete"] = "off"
            if field_name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[field_name]
        self.fields["ativo"].widget.attrs["class"] = "superadmin-form__checkbox"
        self.fields["ocultar_logo_documentos"].widget.attrs["class"] = "superadmin-form__checkbox"
        self.fields["logo_documentos"].widget.attrs["class"] = "company-brand-form__file-input"

    def clean_logo_documentos(self):
        logo = self.cleaned_data.get("logo_documentos")
        if not logo:
            return logo

        if getattr(logo, "size", 0) > 150 * 1024:
            raise forms.ValidationError("Envie uma logo com no maximo 150KB.")

        content_type = getattr(logo, "content_type", "")
        if content_type and content_type != "image/png":
            raise forms.ValidationError("Envie a logo em PNG com fundo transparente.")

        return logo

    def save(self, commit=True):
        instance = super().save(commit=False)
        uploaded_logo = self.files.get("logo_documentos")
        if self.cleaned_data.get("remover_logo_documentos") and not uploaded_logo and instance.logo_documentos:
            instance.logo_documentos.delete(save=False)
            instance.logo_documentos = None
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class AcompanhamentoPassagemForm(forms.ModelForm):
    proxima_verificacao_em = forms.DateTimeField(
        required=False,
        input_formats=["%Y-%m-%dT%H:%M"],
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"}),
    )

    class Meta:
        model = AcompanhamentoPassagem
        fields = [
            "modo_consulta",
            "sistema_origem",
            "referencia_externa",
            "localizador_consulta",
            "sobrenome_consulta",
            "email_consulta",
            "status_reserva",
            "status_voo",
            "ultimo_resumo",
            "orientacao_operacional",
            "proxima_verificacao_em",
            "ativo",
        ]
        widgets = {
            "sistema_origem": forms.TextInput(),
            "referencia_externa": forms.TextInput(),
            "localizador_consulta": forms.TextInput(),
            "sobrenome_consulta": forms.TextInput(),
            "email_consulta": forms.EmailInput(),
            "ultimo_resumo": forms.Textarea(attrs={"rows": 4}),
            "orientacao_operacional": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {
            "modo_consulta": "Origem da consulta",
            "sistema_origem": "Sistema de origem",
            "referencia_externa": "Referencia externa",
            "localizador_consulta": "Localizador para consulta",
            "sobrenome_consulta": "Sobrenome do passageiro",
            "email_consulta": "E-mail de consulta",
            "status_reserva": "Status da reserva",
            "status_voo": "Status do voo",
            "ultimo_resumo": "Resumo operacional",
            "orientacao_operacional": "Orientacao interna",
            "proxima_verificacao_em": "Proxima verificacao",
            "ativo": "Acompanhamento ativo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "sistema_origem": "Ex: consolidator, backoffice, GDS, emissor parceiro",
            "referencia_externa": "Ex: ID da emissao no sistema de origem",
            "localizador_consulta": "Ex: ABC123",
            "sobrenome_consulta": "Ex: Silva",
            "email_consulta": "E-mail usado na consulta, quando aplicavel",
            "ultimo_resumo": "Resumo curto do ultimo retorno operacional.",
            "orientacao_operacional": "Proximos passos, pendencias ou observacoes internas.",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.pop("class", None)
            field.widget.attrs["autocomplete"] = "off"
            if field_name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[field_name]
        self.fields["modo_consulta"].choices = [
            ("", "Selecione o modo"),
            *self.fields["modo_consulta"].choices,
        ]
        self.fields["status_reserva"].choices = [
            ("", "Selecione o status"),
            *self.fields["status_reserva"].choices,
        ]
        self.fields["status_voo"].choices = [
            ("", "Selecione o status"),
            *self.fields["status_voo"].choices,
        ]

    def clean(self):
        cleaned = super().clean()
        modo = cleaned.get("modo_consulta")
        localizador = (cleaned.get("localizador_consulta") or "").strip()
        sobrenome = (cleaned.get("sobrenome_consulta") or "").strip()
        sistema_origem = (cleaned.get("sistema_origem") or "").strip()
        if modo == AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA and not localizador:
            self.add_error("localizador_consulta", "Informe o localizador para consultas no portal da companhia.")
        if modo == AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA and localizador and not sobrenome:
            self.add_error("sobrenome_consulta", "Informe o sobrenome do passageiro para o portal da companhia.")
        if modo == AcompanhamentoPassagem.MODO_SISTEMA_ORIGEM and not sistema_origem:
            self.add_error("sistema_origem", "Informe o nome do sistema de origem.")
        return cleaned


class DocumentoPlataformaForm(forms.ModelForm):
    class Meta:
        model = DocumentoPlataforma
        fields = [
            "versao_atual",
            "data_vigencia",
            "exige_aceite_empresa",
            "ativo",
            "observacoes_internas",
        ]
        widgets = {
            "versao_atual": forms.TextInput(),
            "data_vigencia": forms.DateInput(attrs={"type": "date"}),
            "observacoes_internas": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {
            "versao_atual": "Versao atual",
            "data_vigencia": "Data de vigencia",
            "exige_aceite_empresa": "Exigir aceite do admin da empresa",
            "ativo": "Documento ativo",
            "observacoes_internas": "Observacoes internas",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        placeholders = {
            "versao_atual": "Ex: v1.0",
            "observacoes_internas": "Observacoes operacionais ou juridicas sobre a versao atual.",
        }
        for field_name, field in self.fields.items():
            field.widget.attrs.pop("class", None)
            field.widget.attrs["autocomplete"] = "off"
            if field_name in placeholders:
                field.widget.attrs["placeholder"] = placeholders[field_name]


class CartaoClienteForm(forms.ModelForm):
    # JSON string: [{"nome":"Priority Pass","acessos_titular":4,"acessos_convidados":0},...]
    programas_sala_vip_json = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = CartaoCliente
        fields = [
            "passageiro_frequente",
            "bandeira",
            "categoria",
            "banco",
            "observacoes",
        ]
        widgets = {
            "observacoes": forms.Textarea(attrs={"rows": 2, "placeholder": "Observacoes sobre o cartao"}),
            "banco": forms.TextInput(attrs={"placeholder": "Ex: Itau, Nubank, Bradesco"}),
        }

    def __init__(self, *args, cliente=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["bandeira"].widget.attrs["class"] = ""
        self.fields["categoria"].widget.attrs["class"] = ""
        if cliente:
            self.fields["passageiro_frequente"].queryset = cliente.passageiros_frequentes.all()
        else:
            self.fields["passageiro_frequente"].queryset = PassageiroFrequente.objects.none()
        self.fields["passageiro_frequente"].required = False
        self.fields["passageiro_frequente"].empty_label = "Titular (cliente)"
        if self.instance and self.instance.pk:
            import json as _json
            programas = list(
                self.instance.programas_sala_vip.values("nome", "acessos_titular", "acessos_convidados")
            )
            self.initial["programas_sala_vip_json"] = _json.dumps(programas)
