"""
Views de gestao financeira do painel superadmin NCfly.

Acesso restrito via SuperAdminRequiredMixin — somente pedro@ncfly.com.br.
URL base: /ncadm/financeiro/
"""
import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from onboarding.models import Assinatura, Pagamento, Plano
from .mixins import SuperAdminRequiredMixin
from .services.financeiro import build_financeiro_dashboard_context

logger = logging.getLogger(__name__)

TRANSICOES_VALIDAS = {
    "trial": {"ativa", "inadimplente", "cancelada"},
    "ativa": {"inadimplente", "suspensa", "cancelada"},
    "inadimplente": {"ativa", "suspensa", "cancelada"},
    "suspensa": {"ativa", "cancelada"},
    "cancelada": set(),
}


class FinanceiroDashboardView(SuperAdminRequiredMixin):
    def get(self, request):
        context = build_financeiro_dashboard_context()
        return render(request, "superadmin/financeiro_dashboard.html", context)


class AssinaturasListView(SuperAdminRequiredMixin):
    ITENS_POR_PAGINA = 30

    def get(self, request):
        qs = Assinatura.objects.select_related("empresa", "plano").order_by("-criado_em")

        status_filtro = request.GET.get("status", "")
        plano_filtro = request.GET.get("plano", "").strip()
        busca = request.GET.get("q", "").strip()

        if status_filtro:
            qs = qs.filter(status=status_filtro)
        if plano_filtro:
            qs = qs.filter(plano_id=plano_filtro)
        if busca:
            qs = qs.filter(empresa__nome__icontains=busca)

        paginator = Paginator(qs, self.ITENS_POR_PAGINA)
        page_obj = paginator.get_page(request.GET.get("page", 1))

        planos_disponiveis = Plano.objects.filter(ativo=True).order_by("ordem")

        context = {
            "menu_ativo": "assinaturas",
            "page_obj": page_obj,
            "status_filtro": status_filtro,
            "plano_filtro": plano_filtro,
            "busca": busca,
            "planos_disponiveis": planos_disponiveis,
            "total": qs.count(),
        }
        return render(request, "superadmin/assinaturas_list.html", context)


class AssinaturaDetailView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        assinatura = get_object_or_404(
            Assinatura.objects.select_related("empresa", "plano"), pk=pk
        )
        pagamentos = assinatura.pagamentos.order_by("-criado_em")
        transicoes_permitidas = sorted(
            TRANSICOES_VALIDAS.get(assinatura.status, set())
        )

        context = {
            "menu_ativo": "assinaturas",
            "assinatura": assinatura,
            "pagamentos": pagamentos,
            "transicoes_permitidas": transicoes_permitidas,
        }
        return render(request, "superadmin/assinatura_detail.html", context)


class AssinaturaStatusChangeView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        assinatura = get_object_or_404(
            Assinatura.objects.select_related("empresa", "plano"), pk=pk
        )
        novo_status = request.POST.get("novo_status", "").strip()
        status_atual = assinatura.status
        transicoes_permitidas = TRANSICOES_VALIDAS.get(status_atual, set())

        if novo_status not in transicoes_permitidas:
            messages.error(request, f'Transicao de "{status_atual}" para "{novo_status}" nao permitida.')
            return redirect(reverse("superadmin_assinatura_detail", kwargs={"pk": pk}))

        assinatura.status = novo_status
        if novo_status == "cancelada":
            assinatura.cancelada_em = timezone.now()
        assinatura.save()

        logger.info(
            "Superadmin alterou status da assinatura pk=%s empresa=%r de %r para %r user=%s",
            pk, assinatura.empresa.nome, status_atual, novo_status, request.user.email,
        )
        messages.success(
            request,
            f'Status da assinatura de "{assinatura.empresa.nome}" alterado de "{status_atual}" para "{novo_status}".',
        )
        return redirect(reverse("superadmin_assinatura_detail", kwargs={"pk": pk}))

    def get(self, request, *args, **kwargs):
        messages.error(request, "Metodo nao permitido.")
        return redirect(reverse("superadmin_assinaturas_list"))


class PagamentosListView(SuperAdminRequiredMixin):
    ITENS_POR_PAGINA = 30

    def get(self, request):
        qs = Pagamento.objects.select_related(
            "assinatura__empresa", "assinatura__plano"
        ).order_by("-criado_em")

        status_filtro = request.GET.get("status", "")
        metodo_filtro = request.GET.get("metodo", "")
        busca = request.GET.get("q", "").strip()

        if status_filtro:
            qs = qs.filter(status=status_filtro)
        if metodo_filtro:
            qs = qs.filter(metodo=metodo_filtro)
        if busca:
            qs = qs.filter(assinatura__empresa__nome__icontains=busca)

        paginator = Paginator(qs, self.ITENS_POR_PAGINA)
        page_obj = paginator.get_page(request.GET.get("page", 1))

        context = {
            "menu_ativo": "pagamentos",
            "page_obj": page_obj,
            "status_filtro": status_filtro,
            "metodo_filtro": metodo_filtro,
            "busca": busca,
            "total": qs.count(),
        }
        return render(request, "superadmin/pagamentos_list.html", context)
