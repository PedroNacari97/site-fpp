from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect

from gestao.models import Cliente


@login_required
def assinatura_bloqueada(request):
    """Tela exibida quando a assinatura esta inativa."""
    cliente = getattr(request.user, "cliente_gestao", None)
    empresa = None
    assinatura = None
    try:
        if cliente:
            empresa = cliente.empresa
            assinatura = empresa.assinatura
    except Exception:
        pass

    motivo = ""
    if assinatura:
        if assinatura.status == "trial" and assinatura.trial_expirado:
            motivo = "trial_expirado"
        else:
            motivo = assinatura.status

    return render(request, "onboarding/assinatura_bloqueada.html", {
        "empresa": empresa,
        "assinatura": assinatura,
        "motivo": motivo,
    })
