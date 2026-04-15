"""
Views do painel superadmin NCfly.

Acesso restrito via SuperAdminRequiredMixin — somente pedro@ncfly.com.br.
URL base: /painel-ncfly/
"""
import json
import logging
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from gestao.models import Empresa
from portal.models import NoticiaPublicada, JobExecucao, LeadPlataforma, LeadAlertaEmail

from .mixins import SuperAdminRequiredMixin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardView(SuperAdminRequiredMixin):
    def get(self, request):
        agora = timezone.now()
        ultimas_24h = agora - timedelta(hours=24)
        ultimos_7d = agora - timedelta(days=7)

        total_noticias = NoticiaPublicada.objects.count()
        noticias_publicadas = NoticiaPublicada.objects.filter(status="published").count()
        noticias_draft = NoticiaPublicada.objects.filter(status="draft").count()
        noticias_24h = NoticiaPublicada.objects.filter(criada_em__gte=ultimas_24h).count()

        total_empresas = Empresa.objects.count()
        empresas_ativas = Empresa.objects.filter(ativo=True).count()

        total_leads_plataforma = LeadPlataforma.objects.count()
        leads_novos = LeadPlataforma.objects.filter(status="novo").count()
        leads_7d = LeadPlataforma.objects.filter(criado_em__gte=ultimos_7d).count()

        total_leads_alertas = LeadAlertaEmail.objects.count()
        alertas_ativos = LeadAlertaEmail.objects.filter(status="ativo").count()

        ultimas_noticias = (
            NoticiaPublicada.objects
            .select_related("fonte")
            .order_by("-criada_em")[:10]
        )

        ultimos_jobs = JobExecucao.objects.order_by("-horario")[:5]

        noticias_por_categoria = (
            NoticiaPublicada.objects
            .filter(status="published")
            .values("categoria")
            .annotate(total=Count("id"))
            .order_by("-total")[:8]
        )

        context = {
            "menu_ativo": "dashboard",
            "total_noticias": total_noticias,
            "noticias_publicadas": noticias_publicadas,
            "noticias_draft": noticias_draft,
            "noticias_24h": noticias_24h,
            "total_empresas": total_empresas,
            "empresas_ativas": empresas_ativas,
            "total_leads_plataforma": total_leads_plataforma,
            "leads_novos": leads_novos,
            "leads_7d": leads_7d,
            "total_leads_alertas": total_leads_alertas,
            "alertas_ativos": alertas_ativos,
            "ultimas_noticias": ultimas_noticias,
            "ultimos_jobs": ultimos_jobs,
            "noticias_por_categoria": noticias_por_categoria,
        }
        return render(request, "superadmin/dashboard.html", context)


# ---------------------------------------------------------------------------
# Noticias
# ---------------------------------------------------------------------------

class NoticiasListView(SuperAdminRequiredMixin):
    ITENS_POR_PAGINA = 30

    def get(self, request):
        qs = (
            NoticiaPublicada.objects
            .select_related("fonte")
            .order_by("-criada_em")
        )

        # filtros opcionais
        status_filtro = request.GET.get("status", "").strip()
        busca = request.GET.get("q", "").strip()
        categoria = request.GET.get("categoria", "").strip()

        if status_filtro:
            qs = qs.filter(status=status_filtro)
        if busca:
            qs = qs.filter(titulo__icontains=busca)
        if categoria:
            qs = qs.filter(categoria__icontains=categoria)

        paginator = Paginator(qs, self.ITENS_POR_PAGINA)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        categorias_disponiveis = (
            NoticiaPublicada.objects
            .exclude(categoria="")
            .values_list("categoria", flat=True)
            .distinct()
            .order_by("categoria")
        )

        context = {
            "menu_ativo": "noticias",
            "page_obj": page_obj,
            "status_filtro": status_filtro,
            "busca": busca,
            "categoria": categoria,
            "categorias_disponiveis": categorias_disponiveis,
            "total": qs.count(),
        }
        return render(request, "superadmin/noticias_list.html", context)


class NoticiaDeleteView(SuperAdminRequiredMixin):
    """
    GET  -> exibe pagina de confirmacao
    POST -> executa a exclusao
    """

    def get(self, request, pk):
        noticia = get_object_or_404(NoticiaPublicada, pk=pk)
        context = {
            "menu_ativo": "noticias",
            "noticia": noticia,
        }
        return render(request, "superadmin/noticia_confirma_delete.html", context)

    def post(self, request, pk):
        noticia = get_object_or_404(NoticiaPublicada, pk=pk)
        titulo = noticia.titulo
        noticia.delete()
        logger.info(
            "Superadmin excluiu noticia pk=%s titulo=%r user=%s",
            pk,
            titulo,
            request.user.email,
        )
        messages.success(request, f'Noticia "{titulo}" excluida com sucesso.')
        return redirect(reverse("superadmin_noticias_list"))


# ---------------------------------------------------------------------------
# Artigo upload manual
# ---------------------------------------------------------------------------

class ArtigoUploadView(SuperAdminRequiredMixin):
    """
    Formulario simples para subir um artigo manual (cria NoticiaPublicada diretamente).
    """

    def get(self, request):
        context = {"menu_ativo": "noticias"}
        return render(request, "superadmin/artigo_upload.html", context)

    def post(self, request):
        titulo = request.POST.get("titulo", "").strip()
        resumo = request.POST.get("resumo", "").strip()
        conteudo = request.POST.get("conteudo", "").strip()
        categoria = request.POST.get("categoria", "").strip()
        topico = request.POST.get("topico", "").strip()
        url_fonte = request.POST.get("url_fonte", "").strip()
        status = request.POST.get("status", "draft").strip()
        imagem_file = request.FILES.get("imagem")

        erros = []
        if not titulo:
            erros.append("Titulo e obrigatorio.")
        if not resumo:
            erros.append("Resumo e obrigatorio.")
        if not conteudo:
            erros.append("Conteudo e obrigatorio.")
        if not url_fonte:
            erros.append("URL da fonte e obrigatoria.")
        if status not in ("draft", "published", "archived"):
            status = "draft"

        if erros:
            for erro in erros:
                messages.error(request, erro)
            context = {
                "menu_ativo": "noticias",
                "form_data": request.POST,
            }
            return render(request, "superadmin/artigo_upload.html", context)

        noticia = NoticiaPublicada(
            titulo=titulo,
            resumo=resumo,
            conteudo=conteudo,
            categoria=categoria,
            topico=topico,
            url_fonte=url_fonte,
            status=status,
        )
        if imagem_file:
            noticia.imagem = imagem_file

        noticia.save()

        logger.info(
            "Superadmin criou artigo manual pk=%s titulo=%r user=%s",
            noticia.pk,
            titulo,
            request.user.email,
        )
        messages.success(request, f'Artigo "{titulo}" criado com sucesso (status: {status}).')
        return redirect(reverse("superadmin_noticias_list"))


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

class EmpresasListView(SuperAdminRequiredMixin):
    ITENS_POR_PAGINA = 30

    def get(self, request):
        qs = Empresa.objects.prefetch_related("pessoas").order_by("nome")

        busca = request.GET.get("q", "").strip()
        ativo_filtro = request.GET.get("ativo", "").strip()

        if busca:
            qs = qs.filter(nome__icontains=busca)
        if ativo_filtro == "1":
            qs = qs.filter(ativo=True)
        elif ativo_filtro == "0":
            qs = qs.filter(ativo=False)

        paginator = Paginator(qs, self.ITENS_POR_PAGINA)
        page_obj = paginator.get_page(request.GET.get("page", 1))

        context = {
            "menu_ativo": "empresas",
            "page_obj": page_obj,
            "busca": busca,
            "ativo_filtro": ativo_filtro,
            "total": qs.count(),
        }
        return render(request, "superadmin/empresas_list.html", context)


class EmpresaDetailView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        empresa = get_object_or_404(
            Empresa.objects.prefetch_related("pessoas__usuario"),
            pk=pk,
        )
        context = {
            "menu_ativo": "empresas",
            "empresa": empresa,
        }
        return render(request, "superadmin/empresa_detail.html", context)


class EmpresaCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        context = {"menu_ativo": "empresas"}
        return render(request, "superadmin/empresa_form.html", context)

    def post(self, request):
        nome = request.POST.get("nome", "").strip()
        responsavel_nome = request.POST.get("responsavel_nome", "").strip()
        email_contato = request.POST.get("email_contato", "").strip()
        telefone_contato = request.POST.get("telefone_contato", "").strip()
        whatsapp = request.POST.get("whatsapp", "").strip()
        website = request.POST.get("website", "").strip()
        cidade = request.POST.get("cidade", "").strip()
        estado = request.POST.get("estado", "").strip()
        limite_colaboradores = request.POST.get("limite_colaboradores", "0").strip()
        ativo = request.POST.get("ativo") == "1"

        erros = []
        if not nome:
            erros.append("Nome da empresa e obrigatorio.")
        if Empresa.objects.filter(nome=nome).exists():
            erros.append(f'Ja existe uma empresa com o nome "{nome}".')
        try:
            limite_colaboradores = int(limite_colaboradores)
        except (ValueError, TypeError):
            limite_colaboradores = 0

        if erros:
            for erro in erros:
                messages.error(request, erro)
            context = {
                "menu_ativo": "empresas",
                "form_data": request.POST,
            }
            return render(request, "superadmin/empresa_form.html", context)

        empresa = Empresa.objects.create(
            nome=nome,
            responsavel_nome=responsavel_nome,
            email_contato=email_contato,
            telefone_contato=telefone_contato,
            whatsapp=whatsapp,
            website=website,
            cidade=cidade,
            estado=estado,
            limite_colaboradores=limite_colaboradores,
            ativo=ativo,
        )

        logger.info(
            "Superadmin criou empresa pk=%s nome=%r user=%s",
            empresa.pk,
            nome,
            request.user.email,
        )
        messages.success(request, f'Empresa "{nome}" criada com sucesso.')
        return redirect(reverse("superadmin_empresa_detail", kwargs={"pk": empresa.pk}))


class EmpresaEditView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        empresa = get_object_or_404(Empresa, pk=pk)
        context = {
            "menu_ativo": "empresas",
            "empresa": empresa,
            "editando": True,
        }
        return render(request, "superadmin/empresa_form.html", context)

    def post(self, request, pk):
        empresa = get_object_or_404(Empresa, pk=pk)

        nome = request.POST.get("nome", "").strip()
        responsavel_nome = request.POST.get("responsavel_nome", "").strip()
        email_contato = request.POST.get("email_contato", "").strip()
        telefone_contato = request.POST.get("telefone_contato", "").strip()
        whatsapp = request.POST.get("whatsapp", "").strip()
        website = request.POST.get("website", "").strip()
        cidade = request.POST.get("cidade", "").strip()
        estado = request.POST.get("estado", "").strip()
        limite_colaboradores = request.POST.get("limite_colaboradores", "0").strip()
        ativo = request.POST.get("ativo") == "1"

        erros = []
        if not nome:
            erros.append("Nome da empresa e obrigatorio.")
        if Empresa.objects.filter(nome=nome).exclude(pk=pk).exists():
            erros.append(f'Ja existe outra empresa com o nome "{nome}".')
        try:
            limite_colaboradores = int(limite_colaboradores)
        except (ValueError, TypeError):
            limite_colaboradores = empresa.limite_colaboradores

        if erros:
            for erro in erros:
                messages.error(request, erro)
            context = {
                "menu_ativo": "empresas",
                "empresa": empresa,
                "editando": True,
                "form_data": request.POST,
            }
            return render(request, "superadmin/empresa_form.html", context)

        empresa.nome = nome
        empresa.responsavel_nome = responsavel_nome
        empresa.email_contato = email_contato
        empresa.telefone_contato = telefone_contato
        empresa.whatsapp = whatsapp
        empresa.website = website
        empresa.cidade = cidade
        empresa.estado = estado
        empresa.limite_colaboradores = limite_colaboradores
        empresa.ativo = ativo
        empresa.save()

        logger.info(
            "Superadmin editou empresa pk=%s nome=%r user=%s",
            empresa.pk,
            nome,
            request.user.email,
        )
        messages.success(request, f'Empresa "{nome}" atualizada.')
        return redirect(reverse("superadmin_empresa_detail", kwargs={"pk": empresa.pk}))
