from decimal import Decimal
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.db.models import Sum, Count, Q
from django.utils import timezone

from gestao.models import (
    Cliente,
    CotacaoVoo,
    EmissaoPassagem,
    EmissaoHotel,
    ContaFidelidade,
)
from services.browser_pdf import render_pdf_from_template
from gestao.utils import format_cpf_display
from .permissions import require_admin_or_operator, scope_queryset_to_company


def _fmt_brl(valor):
    """Formata Decimal para R$ 1.234,56"""
    if valor is None:
        return "R$ 0,00"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


@login_required
def relatorio_cliente_pdf(request, cliente_id):
    if bloqueio := require_admin_or_operator(request):
        return bloqueio

    cliente = get_object_or_404(
        scope_queryset_to_company(
            Cliente.objects.select_related("usuario", "empresa"),
            request,
            "empresa",
        ),
        id=cliente_id,
    )

    hoje = timezone.now()
    nome_cliente = cliente.usuario.get_full_name() or cliente.usuario.username

    # ── Cotações ──
    cotacoes_qs = CotacaoVoo.objects.filter(cliente=cliente)
    total_cotacoes = cotacoes_qs.count()
    cotacoes_por_status = {}
    for status, label in CotacaoVoo.STATUS_CHOICES:
        cotacoes_por_status[label] = cotacoes_qs.filter(status=status).count()

    economia_cotacoes = cotacoes_qs.aggregate(
        total=Sum("economia"),
    )["total"] or Decimal("0")

    valor_total_cotacoes = cotacoes_qs.aggregate(
        total=Sum("valor_vista"),
    )["total"] or Decimal("0")

    # Top 5 cotações recentes
    cotacoes_recentes = (
        cotacoes_qs.select_related("origem", "destino", "programa")
        .order_by("-criado_em")[:5]
    )
    cotacoes_lista = []
    for c in cotacoes_recentes:
        cotacoes_lista.append({
            "origem": getattr(c.origem, "iata", "-") if c.origem else "-",
            "destino": getattr(c.destino, "iata", "-") if c.destino else "-",
            "data": c.data_ida.strftime("%d/%m/%Y") if c.data_ida else "-",
            "programa": str(c.programa) if c.programa_id else "-",
            "valor": _fmt_brl(c.valor_vista),
            "economia": _fmt_brl(c.economia),
            "status": c.get_status_display(),
        })

    # ── Emissões ──
    emissoes_qs = EmissaoPassagem.objects.filter(cliente=cliente)
    total_emissoes = emissoes_qs.count()
    emissoes_com_loc = emissoes_qs.exclude(localizador="").exclude(localizador__isnull=True)
    total_emitidas = emissoes_com_loc.count()
    total_pendentes = total_emissoes - total_emitidas

    receita_emissoes = emissoes_qs.aggregate(
        total=Sum("valor_cobrado_cliente"),
    )["total"] or Decimal("0")

    lucro_emissoes = emissoes_qs.aggregate(
        total=Sum("lucro"),
    )["total"] or Decimal("0")

    # Top 5 emissões recentes
    emissoes_recentes = (
        emissoes_qs.select_related("aeroporto_partida", "aeroporto_destino", "programa")
        .order_by("-criado_em")[:5]
    )
    emissoes_lista = []
    for e in emissoes_recentes:
        emissoes_lista.append({
            "origem": getattr(e.aeroporto_partida, "iata", "-") if e.aeroporto_partida else "-",
            "destino": getattr(e.aeroporto_destino, "iata", "-") if e.aeroporto_destino else "-",
            "data": e.data_ida.strftime("%d/%m/%Y") if e.data_ida else "-",
            "programa": str(e.programa) if e.programa_id else "-",
            "valor": _fmt_brl(e.valor_cobrado_cliente),
            "localizador": e.localizador or "Pendente",
        })

    # ── Hotéis ──
    hoteis_qs = EmissaoHotel.objects.filter(cliente=cliente)
    total_hoteis = hoteis_qs.count()
    economia_hoteis = hoteis_qs.aggregate(
        total=Sum("economia_obtida"),
    )["total"] or Decimal("0")
    valor_hoteis = hoteis_qs.aggregate(
        total=Sum("valor_pago"),
    )["total"] or Decimal("0")

    # ── Contas de Fidelidade (pontos) ──
    contas = (
        ContaFidelidade.objects.filter(cliente=cliente)
        .select_related("programa")
        .order_by("programa__nome")
    )
    contas_lista = []
    for conta in contas:
        contas_lista.append({
            "programa": str(conta.programa),
            "clube": conta.get_clube_periodicidade_display() if conta.clube_periodicidade != "nenhum" else "Sem clube",
            "pontos_mes": f"{conta.pontos_clube_mes:,}".replace(",", ".") if conta.pontos_clube_mes else "-",
            "validade": conta.validade.strftime("%d/%m/%Y") if conta.validade else "Sem validade definida",
        })

    # ── Economia total ──
    economia_total = economia_cotacoes + economia_hoteis

    # ── Resumo geral ──
    resumo = {
        "nome": nome_cliente,
        "email": cliente.usuario.email,
        "telefone": cliente.telefone or "-",
        "cpf": format_cpf_display(cliente.cpf or "", fallback="-"),
        "empresa": str(cliente.empresa) if cliente.empresa else "-",
        "data_relatorio": hoje.strftime("%d/%m/%Y %H:%M"),
    }

    indicadores = [
        {"label": "Viagens cotadas", "valor": str(total_cotacoes)},
        {"label": "Cotações aprovadas", "valor": str(cotacoes_por_status.get("Aceita", 0) + cotacoes_por_status.get("Emissão", 0))},
        {"label": "Passagens emitidas", "valor": str(total_emitidas)},
        {"label": "Reservas de hotel", "valor": str(total_hoteis)},
        {"label": "Programas ativos", "valor": str(len(contas_lista))},
    ]

    # Nota: não exibimos lucro da agência nem login de programa de fidelidade
    # neste relatório — é um documento que vai para o cliente final.
    valores = [
        {"label": "Você investiu em passagens", "valor": _fmt_brl(receita_emissoes)},
        {"label": "Você investiu em hotéis", "valor": _fmt_brl(valor_hoteis)},
        {"label": "Economia em passagens", "valor": _fmt_brl(economia_cotacoes), "destaque": True},
        {"label": "Economia em hotéis", "valor": _fmt_brl(economia_hoteis), "destaque": True},
        {"label": "Economia total no período", "valor": _fmt_brl(economia_total), "destaque": True},
    ]

    # Próximos passos dependem de cotações ainda em aberto
    cotacoes_em_aberto = (
        cotacoes_por_status.get("Enviada", 0)
        + cotacoes_por_status.get("Aceita", 0)
    )
    emissoes_pendentes = total_pendentes

    context = {
        "cliente": cliente,
        "resumo": resumo,
        "indicadores": indicadores,
        "valores": valores,
        "cotacoes_por_status": cotacoes_por_status,
        "cotacoes_lista": cotacoes_lista,
        "emissoes_lista": emissoes_lista,
        "contas_lista": contas_lista,
        "economia_total": _fmt_brl(economia_total),
        "cotacoes_em_aberto": cotacoes_em_aberto,
        "emissoes_pendentes": emissoes_pendentes,
        "tem_dados": bool(total_cotacoes or total_emissoes or total_hoteis or contas_lista),
    }

    try:
        pdf = render_pdf_from_template(
            "admin_custom/pdf/relatorio_cliente_pdf.html",
            context,
            css_paths=(
                "gestao/css/base/variables.css",
                "gestao/css/cotacao_preview.css",
            ),
        )
    except Exception as exc:
        from django.http import HttpResponse
        return HttpResponse(f"Erro ao gerar PDF: {exc}", status=500)

    buffer = BytesIO(pdf)
    buffer.seek(0)
    slug = nome_cliente.replace(" ", "_").lower()[:30]
    return FileResponse(
        buffer,
        as_attachment=False,
        filename=f"relatorio_{slug}_{hoje.strftime('%Y%m%d')}.pdf",
    )
