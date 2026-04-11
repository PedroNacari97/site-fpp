import re

from django import forms
from django.utils import timezone

from .models import LeadAlertaEmail, LeadPlataforma


def _format_br_phone(value):
    digits = re.sub(r"\D+", "", str(value or ""))
    if digits.startswith("55") and len(digits) >= 12:
        digits = digits[2:]
    digits = digits[:11]
    if not digits:
        return ""
    if len(digits) <= 2:
        return f"({digits}"
    if len(digits) <= 6:
        return f"({digits[:2]}) {digits[2:]}"
    if len(digits) <= 10:
        return f"({digits[:2]}) {digits[2:6]}-{digits[6:]}"
    return f"({digits[:2]}) {digits[2:7]}-{digits[7:]}"


class PlataformaLeadForm(forms.ModelForm):
    lead_terms_accept = forms.CharField(
        required=False,
        widget=forms.HiddenInput(
            attrs={
                "value": "",
                "data-lead-consent-input": "1",
            }
        ),
    )

    class Meta:
        model = LeadPlataforma
        fields = [
            "nome_completo",
            "empresa",
            "cargo",
            "email",
            "telefone",
            "equipe_tamanho",
            "mensagem",
        ]
        widgets = {
            "nome_completo": forms.TextInput(
                attrs={
                    "class": "portal-lead-field__input",
                    "placeholder": "Seu nome completo",
                    "autocomplete": "name",
                }
            ),
            "empresa": forms.TextInput(
                attrs={
                    "class": "portal-lead-field__input",
                    "placeholder": "Nome da empresa",
                    "autocomplete": "organization",
                }
            ),
            "cargo": forms.TextInput(
                attrs={
                    "class": "portal-lead-field__input",
                    "placeholder": "Seu cargo (opcional)",
                    "autocomplete": "organization-title",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "portal-lead-field__input",
                    "placeholder": "seu@email.com",
                    "autocomplete": "email",
                }
            ),
            "telefone": forms.TextInput(
                attrs={
                    "class": "portal-lead-field__input",
                    "placeholder": "(00) 00000-0000",
                    "autocomplete": "tel",
                    "inputmode": "tel",
                    "maxlength": "15",
                    "data-phone-mask": "br",
                }
            ),
            "equipe_tamanho": forms.Select(
                attrs={
                    "class": "portal-lead-field__input portal-lead-field__select",
                }
            ),
            "mensagem": forms.Textarea(
                attrs={
                    "class": "portal-lead-field__input portal-lead-field__textarea",
                    "placeholder": "Conte um pouco sobre sua operacao, volume ou o que voce quer organizar primeiro.",
                    "rows": 4,
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome_completo"].label = "Nome"
        self.fields["empresa"].label = "Empresa"
        self.fields["cargo"].label = "Cargo"
        self.fields["email"].label = "E-mail"
        self.fields["telefone"].label = "Telefone"
        self.fields["equipe_tamanho"].label = "Tamanho da equipe"
        self.fields["mensagem"].label = "Contexto"
        self.fields["equipe_tamanho"].required = False
        self.fields["cargo"].required = False
        self.fields["mensagem"].required = False
        self.fields["equipe_tamanho"].choices = [
            ("", "Selecione"),
            *LeadPlataforma.EQUIPE_TAMANHO_CHOICES,
        ]

    def clean_lead_terms_accept(self):
        if self.cleaned_data.get("lead_terms_accept") != "1":
            raise forms.ValidationError(
                "Abra o termo de aceite, role ate o final e confirme para continuar."
            )
        return "1"

    def clean_telefone(self):
        return _format_br_phone(self.cleaned_data.get("telefone", ""))


class PlataformaQuickLeadForm(forms.Form):
    nome = forms.CharField(
        max_length=180,
        widget=forms.TextInput(
            attrs={
                "class": "portal-lead-field__input",
                "placeholder": "Seu nome",
                "autocomplete": "name",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "portal-lead-field__input",
                "placeholder": "seu@email.com",
                "autocomplete": "email",
            }
        ),
    )
    telefone = forms.CharField(
        required=False,
        max_length=40,
        widget=forms.TextInput(
            attrs={
                "class": "portal-lead-field__input",
                "placeholder": "(00) 00000-0000",
                "autocomplete": "tel",
                "inputmode": "tel",
                "maxlength": "15",
                "data-phone-mask": "br",
            }
        ),
    )
    aceite_contato = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome"].label = "Nome"
        self.fields["email"].label = "E-mail"
        self.fields["telefone"].label = "Telefone"
        self.fields["aceite_contato"].label = (
            "Autorizo o contato da NC Fly sobre a plataforma e li a Política de Privacidade."
        )

    def clean_telefone(self):
        return _format_br_phone(self.cleaned_data.get("telefone", ""))

    def save(self, *, consent_version="", ip="", user_agent="", source_environment="local", source_host=""):
        return LeadPlataforma.objects.create(
            nome_completo=self.cleaned_data["nome"],
            empresa="",
            cargo="",
            email=self.cleaned_data["email"],
            telefone=self.cleaned_data.get("telefone", ""),
            equipe_tamanho="",
            mensagem="Lead rapido captado pela pagina da Plataforma NC Fly.",
            aceite_versao=consent_version,
            aceito_em=timezone.now(),
            aceito_ip=ip,
            aceito_user_agent=user_agent[:255],
            source_environment=(source_environment or "local")[:20],
            source_host=(source_host or "")[:120],
            status=LeadPlataforma.STATUS_CHOICES[0][0],
        )


class AlertEmailLeadForm(forms.Form):
    nome_completo = forms.CharField(
        max_length=180,
        widget=forms.TextInput(
            attrs={
                "class": "portal-lead-field__input",
                "placeholder": "Seu nome completo",
                "autocomplete": "name",
            }
        ),
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "portal-lead-field__input",
                "placeholder": "seu@email.com",
                "autocomplete": "email",
            }
        ),
    )
    telefone = forms.CharField(
        max_length=40,
        widget=forms.TextInput(
            attrs={
                "class": "portal-lead-field__input",
                "placeholder": "(00) 00000-0000",
                "autocomplete": "tel",
                "inputmode": "tel",
                "maxlength": "15",
                "data-phone-mask": "br",
            }
        ),
    )
    aceite_alertas = forms.BooleanField(required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["nome_completo"].label = "Nome"
        self.fields["email"].label = "E-mail"
        self.fields["telefone"].label = "Telefone"
        self.fields["aceite_alertas"].label = "Li e aceito o recebimento de alertas"
        self.fields["aceite_alertas"].error_messages = {
            "required": "Você precisa aceitar os termos de recebimento de alertas para continuar.",
        }

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        existing = LeadAlertaEmail.objects.filter(email=email).only("status").first()
        if existing and existing.status == LeadAlertaEmail.STATUS_ATIVO:
            raise forms.ValidationError("Este e-mail ja esta cadastrado para receber alertas.")
        return email

    def clean_telefone(self):
        return _format_br_phone(self.cleaned_data.get("telefone", ""))

    def save(
        self,
        *,
        consent_version="",
        ip="",
        user_agent="",
        source_environment="local",
        source_host="",
        source_page=LeadAlertaEmail.ORIGEM_ALERTAS,
    ):
        lead, created = LeadAlertaEmail.objects.update_or_create(
            email=self.cleaned_data["email"],
            defaults={
                "nome_completo": self.cleaned_data["nome_completo"],
                "telefone": self.cleaned_data["telefone"],
                "origem_cadastro": source_page,
                "aceite_versao": consent_version,
                "aceito_em": timezone.now(),
                "aceito_ip": ip,
                "aceito_user_agent": (user_agent or "")[:255],
                "source_environment": (source_environment or "local")[:20],
                "source_host": (source_host or "")[:120],
                "status": LeadAlertaEmail.STATUS_ATIVO,
                "motivo_cancelamento": "",
                "cancelado_em": None,
            },
        )
        return lead, created


class AlertEmailUnsubscribeForm(forms.Form):
    motivo = forms.ChoiceField(
        choices=LeadAlertaEmail.MOTIVO_CANCELAMENTO_CHOICES,
        widget=forms.RadioSelect,
        error_messages={
            "required": "Selecione um motivo para confirmar o cancelamento.",
        },
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["motivo"].label = "Motivo do cancelamento"
