from django.contrib.auth.decorators import login_required
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from gestao.models import AcompanhamentoPassagem, AtualizacaoEmMassa, EmissaoPassagem
from gestao.services.acompanhamento_passagem import (
    ensure_acompanhamento_passagem,
    sync_acompanhamento_passagem,
)
from gestao.services.monitoring.bulk_runner import disparar_atualizacao_em_massa
from gestao.views.permissions import (
    ensure_company_access,
    get_request_empresa,
    require_admin_or_operator,
)


@csrf_exempt
@require_http_methods(["GET", "POST", "HEAD"])
def monitoramento_unsubscribe(request, token):
    """Permite que o destinatário do email pare de receber alertas dessa passagem.

    Endpoint público (sem login) chamado pelo link no rodapé do email e pelo
    header ``List-Unsubscribe`` (RFC 8058 — One-Click). Em GET mostra confirmação,
    em POST/HEAD desativa imediatamente.
    """
    try:
        acompanhamento = get_object_or_404(
            AcompanhamentoPassagem.objects.select_related(
                "emissao__companhia_aerea",
                "emissao__cliente__empresa",
            ),
            opt_out_token=token,
        )
    except (ValueError, Http404):
        raise Http404("Token de unsubscribe inválido.")

    if request.method in {"POST", "HEAD"}:
        if acompanhamento.notificar_passageiro:
            acompanhamento.notificar_passageiro = False
            acompanhamento.save(update_fields=["notificar_passageiro", "atualizado_em"])
        return render(
            request,
            "monitoramento/unsubscribe_confirmado.html",
            {"acompanhamento": acompanhamento},
            status=200,
        )

    return render(
        request,
        "monitoramento/unsubscribe.html",
        {"acompanhamento": acompanhamento},
    )


def _serializar_job(job: AtualizacaoEmMassa) -> dict:
    iniciado = job.iniciado_em.isoformat() if job.iniciado_em else None
    concluido = job.concluido_em.isoformat() if job.concluido_em else None
    return {
        "id": job.pk,
        "status": job.status,
        "status_label": job.get_status_display(),
        "total": job.total,
        "ok": job.ok,
        "sem_mudanca": job.sem_mudanca,
        "com_mudanca": job.com_mudanca,
        "erro": job.erro,
        "progresso_pct": job.progresso_pct,
        "em_andamento": job.em_andamento,
        "iniciado_em": iniciado,
        "concluido_em": concluido,
        "mensagem_erro": job.mensagem_erro,
        "resultado": list(job.resultado or [])[-50:],
    }


@login_required
@require_POST
def atualizar_status_passagem(request, emissao_id: int):
    """CTA por linha: atualiza UMA emissão (sync).

    Rápido (1-3s); roda inline e devolve JSON com antes/depois pra UI atualizar.
    """
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    emissao = get_object_or_404(EmissaoPassagem, pk=emissao_id)
    if denied := ensure_company_access(request, emissao):
        return denied

    acompanhamento = ensure_acompanhamento_passagem(emissao)
    antes_reserva = acompanhamento.get_status_reserva_display()
    antes_voo = acompanhamento.get_status_voo_display()

    resultado = sync_acompanhamento_passagem(acompanhamento)
    acompanhamento.refresh_from_db()

    depois_reserva = acompanhamento.get_status_reserva_display()
    depois_voo = acompanhamento.get_status_voo_display()
    teve_mudanca = (antes_reserva != depois_reserva) or (antes_voo != depois_voo)

    return JsonResponse(
        {
            "sucesso": resultado.success,
            "mensagem": resultado.message,
            "teve_mudanca": teve_mudanca,
            "antes": {"reserva": antes_reserva, "voo": antes_voo},
            "depois": {"reserva": depois_reserva, "voo": depois_voo},
            "ultima_sincronizacao": (
                acompanhamento.ultima_sincronizacao_em.isoformat()
                if acompanhamento.ultima_sincronizacao_em
                else None
            ),
        }
    )


@login_required
@require_POST
def atualizar_status_empresa(request):
    """CTA do header: dispara atualização em massa em background."""
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    empresa = get_request_empresa(request)
    if not empresa:
        return JsonResponse(
            {"sucesso": False, "mensagem": "Sua conta não está vinculada a uma empresa."},
            status=400,
        )

    apenas_companhia = request.POST.get("companhia") or None
    dispatch = disparar_atualizacao_em_massa(
        empresa,
        iniciado_por=request.user,
        apenas_companhia_codigo=apenas_companhia,
    )
    payload = {
        "sucesso": dispatch.aceito,
        "mensagem": dispatch.motivo or "Atualização disparada.",
        "job": _serializar_job(dispatch.job),
    }
    return JsonResponse(payload, status=202 if dispatch.aceito else 409)


@login_required
@require_GET
def status_atualizacao_em_massa(request, job_id: int):
    """Endpoint de polling do frontend (3-5s)."""
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    empresa = get_request_empresa(request)
    job = get_object_or_404(AtualizacaoEmMassa, pk=job_id)
    if empresa and job.empresa_id != empresa.pk and not request.user.is_superuser:
        # 404 (não 403) para não revelar IDs entre tenants.
        raise Http404("Job não encontrado.")

    return JsonResponse({"sucesso": True, "job": _serializar_job(job)})


@login_required
@require_GET
def ultimo_job_empresa(request):
    """Retorna o job mais recente da empresa do usuário (pra UI carregar).

    Útil quando o operador abre a tela e precisa saber se há job rodando.
    """
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    empresa = get_request_empresa(request)
    if not empresa:
        return JsonResponse({"sucesso": True, "job": None})
    job = (
        AtualizacaoEmMassa.objects.filter(empresa=empresa)
        .order_by("-iniciado_em")
        .first()
    )
    return JsonResponse({"sucesso": True, "job": _serializar_job(job) if job else None})
