"""Views de moderacao de comentarios (ncadm).

Acesso restrito ao SuperAdmin. URLs montadas em /ncadm/comentarios/.

Endpoints:
- GET  /ncadm/comentarios/                         -> lista com filtros
- POST /ncadm/comentarios/<id>/ocultar/            -> oculta (soft delete)
- POST /ncadm/comentarios/<id>/restaurar/          -> restaura publicado
- POST /ncadm/comentarios/<id>/responder/          -> cria resposta como Pedro
"""
from __future__ import annotations

import logging

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from portal.models import ArtigoEstudo, ComentarioArtigo, PortalUser
from portal.services import comentarios as comentarios_service
from portal.services.comentarios import ComentarioError

from .mixins import SuperAdminRequiredMixin


logger = logging.getLogger(__name__)


class ComentariosListView(SuperAdminRequiredMixin):
    ITENS_POR_PAGINA = 30

    def get(self, request):
        qs = (
            ComentarioArtigo.objects
            .select_related("artigo", "artigo__modulo", "autor", "parent")
            .order_by("-criado_em")
        )

        busca = (request.GET.get("q") or "").strip()
        status_filtro = (request.GET.get("status") or "").strip()
        artigo_id = (request.GET.get("artigo") or "").strip()

        if busca:
            qs = qs.filter(
                Q(corpo__icontains=busca)
                | Q(autor_email_snapshot__icontains=busca)
                | Q(autor_nome_snapshot__icontains=busca)
            )
        if status_filtro in {
            ComentarioArtigo.STATUS_PUBLICADO,
            ComentarioArtigo.STATUS_OCULTO_ADMIN,
            ComentarioArtigo.STATUS_EXCLUIDO_AUTOR,
        }:
            qs = qs.filter(status=status_filtro)
        if artigo_id:
            try:
                qs = qs.filter(artigo_id=int(artigo_id))
            except (TypeError, ValueError):
                pass

        total = qs.count()
        paginator = Paginator(qs, self.ITENS_POR_PAGINA)
        page = paginator.get_page(request.GET.get("page", 1))

        # KPIs
        kpis = {
            "total": ComentarioArtigo.objects.count(),
            "publicados": ComentarioArtigo.objects.filter(status=ComentarioArtigo.STATUS_PUBLICADO).count(),
            "ocultos": ComentarioArtigo.objects.filter(status=ComentarioArtigo.STATUS_OCULTO_ADMIN).count(),
            "excluidos": ComentarioArtigo.objects.filter(status=ComentarioArtigo.STATUS_EXCLUIDO_AUTOR).count(),
        }

        return render(request, "superadmin/comentarios_list.html", {
            "menu_ativo": "comentarios",
            "page_obj": page,
            "comentarios": page,
            "total": total,
            "kpis": kpis,
            "busca": busca,
            "status_filter": status_filtro,
            "artigo_filter": artigo_id,
        })


class ComentarioOcultarView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        comentario = get_object_or_404(ComentarioArtigo, pk=pk)
        motivo = (request.POST.get("motivo") or "").strip()
        if not motivo:
            messages.error(request, "Informe um motivo ao ocultar.")
            return redirect(reverse("superadmin_comentarios_list"))
        try:
            comentarios_service.ocultar_pelo_admin(
                comentario=comentario,
                admin_user=request.user,
                motivo=motivo,
            )
            messages.success(request, "Comentario ocultado.")
        except ComentarioError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("superadmin_comentarios_list"))

    # GET tambem funciona como link direto do email (conveniencia)
    def get(self, request, pk):
        comentario = get_object_or_404(ComentarioArtigo, pk=pk)
        return render(request, "superadmin/comentario_ocultar.html", {
            "menu_ativo": "comentarios",
            "comentario": comentario,
        })


class ComentarioRestaurarView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        comentario = get_object_or_404(ComentarioArtigo, pk=pk)
        try:
            comentarios_service.restaurar_pelo_admin(comentario=comentario)
            messages.success(request, "Comentario restaurado.")
        except ComentarioError as exc:
            messages.error(request, str(exc))
        return redirect(reverse("superadmin_comentarios_list"))


class ComentarioResponderView(SuperAdminRequiredMixin):
    """Admin responde como Pedro via painel — precisa ter PortalUser do Pedro.

    Se o admin ainda nao tem PortalUser, cria um on-the-fly com email do Pedro.
    """

    def post(self, request, pk):
        parent = get_object_or_404(
            ComentarioArtigo.objects.select_related("artigo"),
            pk=pk,
        )
        corpo = (request.POST.get("corpo") or "").strip()
        if not corpo:
            messages.error(request, "Resposta vazia.")
            return redirect(reverse("superadmin_comentarios_list"))

        admin_email = (request.user.email or "").strip().lower()
        admin_nome = (request.user.get_full_name() or request.user.email or "Equipe NC Fly").strip()

        portal_user, _ = PortalUser.objects.get_or_create(
            email=admin_email,
            defaults={
                "nome": admin_nome,
                "ativo": True,
                "email_verificado": True,
            },
        )

        try:
            comentarios_service.criar_comentario(
                artigo=parent.artigo,
                autor=portal_user,
                corpo=corpo,
                parent_id=parent.pk,
                ip=request.META.get("REMOTE_ADDR") or None,
                user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
                exibir_nome_completo=True,
            )
            messages.success(request, "Resposta publicada.")
        except ComentarioError as exc:
            messages.error(request, str(exc))

        return redirect(reverse("superadmin_comentarios_list"))
