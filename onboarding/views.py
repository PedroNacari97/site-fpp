import hashlib
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login
from django.contrib.auth.decorators import login_required
from django.core import signing
from django.db import transaction
from django.shortcuts import redirect, render
from django.utils import timezone
from datetime import timedelta

from accounts.security import get_request_url
from gestao.models import Cliente, Empresa, DocumentoPlataforma, AceiteDocumentoPlataforma
from gestao.utils import generate_unique_username, hash_cpf, normalize_cpf

from .forms import OnboardingStep1Form, OnboardingStep2Form, OnboardingStep3Form, OnboardingStep4Form
from .models import Assinatura, Plano

logger = logging.getLogger(__name__)
User = get_user_model()

ONBOARDING_SESSION_KEY = "_onboarding_data"

STEPS = [
    (1, "Conta"),
    (2, "Empresa"),
    (3, "Contrato"),
    (4, "Plano"),
]


def _get_onboarding_data(request):
    return request.session.get(ONBOARDING_SESSION_KEY, {})


def _set_onboarding_data(request, data):
    request.session[ONBOARDING_SESSION_KEY] = data


def _clear_onboarding_data(request):
    request.session.pop(ONBOARDING_SESSION_KEY, None)


def landing(request):
    """Landing page com planos."""
    planos = Plano.objects.filter(ativo=True).order_by("ordem")
    ref = request.GET.get("ref", "")
    return render(request, "onboarding/landing.html", {
        "planos": planos,
        "ref": ref,
    })


def step1(request):
    """Etapa 1 — Dados do responsavel."""
    data = _get_onboarding_data(request)
    initial = data.get("step1", {})

    if request.method == "POST":
        form = OnboardingStep1Form(request.POST)
        if form.is_valid():
            step_data = form.cleaned_data.copy()
            step_data["password"] = signing.dumps(step_data["password"])
            step_data.pop("confirm_password", None)
            data["step1"] = step_data
            _set_onboarding_data(request, data)
            return redirect("onboarding_step2")
    else:
        form = OnboardingStep1Form(initial=initial)

    return render(request, "onboarding/step1.html", {
        "form": form,
        "current_step": 1,
        "steps": STEPS,
    })


def step2(request):
    """Etapa 2 — Dados da empresa."""
    data = _get_onboarding_data(request)
    if "step1" not in data:
        return redirect("onboarding_step1")

    initial = data.get("step2", {})

    if request.method == "POST":
        form = OnboardingStep2Form(request.POST)
        if form.is_valid():
            data["step2"] = form.cleaned_data
            _set_onboarding_data(request, data)
            return redirect("onboarding_step3")
    else:
        form = OnboardingStep2Form(initial=initial)

    return render(request, "onboarding/step2.html", {
        "form": form,
        "current_step": 2,
        "steps": STEPS,
    })


def step3(request):
    """Etapa 3 — Aceite do contrato."""
    data = _get_onboarding_data(request)
    if "step2" not in data:
        return redirect("onboarding_step2")

    documentos = DocumentoPlataforma.objects.filter(ativo=True, exige_aceite_empresa=True)

    if request.method == "POST":
        form = OnboardingStep3Form(request.POST)
        if form.is_valid():
            data["step3"] = {
                "aceite_termos": True,
                "aceite_privacidade": True,
                "aceite_dpa": True,
                "ip": request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", "")),
                "user_agent": request.META.get("HTTP_USER_AGENT", "")[:255],
                "url_origem": get_request_url(request),
                "device_language": request.META.get("HTTP_ACCEPT_LANGUAGE", "")[:40],
                "device_type": request.POST.get("device_type", "")[:20],
                "browser_name": request.POST.get("browser_name", "")[:60],
                "browser_version": request.POST.get("browser_version", "")[:60],
                "os_name": request.POST.get("os_name", "")[:60],
                "os_version": request.POST.get("os_version", "")[:60],
                "device_timezone": request.POST.get("device_timezone", "")[:80],
                "screen_resolution": request.POST.get("screen_resolution", "")[:40],
            }
            _set_onboarding_data(request, data)
            return redirect("onboarding_step4")
    else:
        form = OnboardingStep3Form()

    return render(request, "onboarding/step3.html", {
        "form": form,
        "documentos": documentos,
        "current_step": 3,
        "steps": STEPS,
    })


def step4(request):
    """Etapa 4 — Escolha do plano e finalizacao."""
    data = _get_onboarding_data(request)
    if "step3" not in data:
        return redirect("onboarding_step3")

    planos = Plano.objects.filter(ativo=True).order_by("ordem")
    ref = request.GET.get("ref", "") or data.get("ref", "")

    if request.method == "POST":
        form = OnboardingStep4Form(request.POST)
        if form.is_valid():
            plano_slug = form.cleaned_data["plano_slug"]
            ref_vendedor = form.cleaned_data.get("ref_vendedor", "")

            try:
                plano = Plano.objects.get(slug=plano_slug, ativo=True)
            except Plano.DoesNotExist:
                messages.error(request, "Plano invalido.")
                return redirect("onboarding_step4")

            try:
                user, empresa = _finalize_onboarding(request, data, plano, ref_vendedor)
            except Exception as e:
                logger.exception("Erro ao finalizar onboarding")
                messages.error(request, f"Erro ao criar conta: {e}")
                return redirect("onboarding_step4")

            _clear_onboarding_data(request)
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, f"Bem-vindo ao NCfly! Seu trial de {plano.trial_dias} dias esta ativo.")
            return redirect("onboarding_welcome")
    else:
        form = OnboardingStep4Form(initial={"plano_slug": planos.filter(destaque=True).first().slug if planos.filter(destaque=True).exists() else ""})

    return render(request, "onboarding/step4.html", {
        "form": form,
        "planos": planos,
        "ref": ref,
        "current_step": 4,
        "steps": STEPS,
    })


@login_required
def welcome(request):
    """Pagina de boas-vindas pos-onboarding."""
    user = request.user
    cliente = getattr(user, "cliente_gestao", None)
    empresa = None
    assinatura = None
    plano_nome = ""
    trial_dias = 0
    trial_fim = None

    if cliente and cliente.empresa_id:
        empresa = cliente.empresa
        try:
            assinatura = empresa.assinatura
            plano_nome = assinatura.plano.nome
            trial_dias = assinatura.plano.trial_dias
            trial_fim = assinatura.trial_fim
        except Exception:
            pass

    return render(request, "onboarding/welcome.html", {
        "user": user,
        "empresa_nome": empresa.nome if empresa else "",
        "plano_nome": plano_nome,
        "trial_dias": trial_dias,
        "trial_fim": trial_fim,
    })


def _finalize_onboarding(request, data, plano, ref_vendedor):
    """Cria User, Cliente, Empresa, Assinatura e registra aceites."""
    s1 = data["step1"]
    s2 = data["step2"]
    s3 = data["step3"]

    raw_password = signing.loads(s1["password"])

    with transaction.atomic():
        # 1. Criar User
        username = generate_unique_username("agency")
        user = User.objects.create_user(
            username=username,
            email=s1["email"],
            password=raw_password,
            first_name=s1["first_name"],
            last_name=s1["last_name"],
        )
        user.is_staff = True
        user.save(update_fields=["is_staff"])

        # 2. Criar Empresa
        empresa = Empresa.objects.create(
            nome=s2["nome_fantasia"],
            tipo_pessoa=s2["tipo_pessoa"],
            cnpj=s2.get("cnpj") or None,
            razao_social=s2.get("razao_social", ""),
            documento_titular=normalize_cpf(s1["cpf"]) if s2["tipo_pessoa"] == "PF" else (s2.get("cnpj") or ""),
            cep=s2.get("cep", ""),
            endereco=s2.get("endereco", ""),
            numero=s2.get("numero", ""),
            complemento=s2.get("complemento", ""),
            bairro=s2.get("bairro", ""),
            cidade=s2.get("cidade", ""),
            estado=s2.get("estado", ""),
            website=s2.get("website", ""),
            email_contato=s1["email"],
            telefone_contato=s1.get("telefone", ""),
            responsavel_nome=f"{s1['first_name']} {s1['last_name']}",
            limite_colaboradores=plano.limite_operadores,
            origem="onboarding",
            ativo=True,
        )

        # 3. Criar Cliente (admin da empresa)
        cliente = Cliente.objects.create(
            usuario=user,
            empresa=empresa,
            cpf=normalize_cpf(s1["cpf"]),
            perfil="admin",
            telefone=s1.get("telefone", ""),
            ativo=True,
        )
        empresa.admin = cliente
        empresa.save(update_fields=["admin"])

        # 4. Criar Assinatura (trial)
        Assinatura.objects.create(
            empresa=empresa,
            plano=plano,
            status=Assinatura.STATUS_TRIAL,
            trial_fim=timezone.now() + timedelta(days=plano.trial_dias),
            ref_vendedor=ref_vendedor,
        )

        # 5. Registrar aceites dos documentos
        documentos = DocumentoPlataforma.objects.filter(
            ativo=True, exige_aceite_empresa=True
        )
        for doc in documentos:
            content_hash = hashlib.sha256(
                (doc.conteudo or "").encode("utf-8")
            ).hexdigest()
            AceiteDocumentoPlataforma.objects.create(
                empresa=empresa,
                documento=doc,
                versao_aceita=doc.versao_atual,
                hash_documento=content_hash,
                aceito_por=user,
                ip_aceite=s3.get("ip", ""),
                user_agent_aceite=s3.get("user_agent", ""),
                url_origem=s3.get("url_origem", ""),
                device_type=s3.get("device_type", ""),
                browser_name=s3.get("browser_name", ""),
                browser_version=s3.get("browser_version", ""),
                os_name=s3.get("os_name", ""),
                os_version=s3.get("os_version", ""),
                device_language=s3.get("device_language", ""),
                device_timezone=s3.get("device_timezone", ""),
                screen_resolution=s3.get("screen_resolution", ""),
            )

        logger.info(
            "Onboarding concluido: empresa=%s user=%s plano=%s",
            empresa.pk, user.pk, plano.slug,
        )

    return user, empresa
