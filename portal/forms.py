from django import forms
from django.utils import timezone

from .models import LeadPlataforma


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
