"""
Views do painel superadmin NCfly.

Acesso restrito via SuperAdminRequiredMixin — somente pedro@ncfly.com.br.
URL base: /ncadm/
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
from django.http import JsonResponse
from portal.models import (
    NoticiaPublicada, JobExecucao, LeadPlataforma, LeadAlertaEmail,
    ModuloEstudo, ArtigoEstudo, ArtigoVideoYoutube,
)

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


# ---------------------------------------------------------------------------
# Artigos Educativos — CRUD
# ---------------------------------------------------------------------------

class ArtigosListView(SuperAdminRequiredMixin):
    def get(self, request):
        qs = ArtigoEstudo.objects.select_related("modulo").order_by("-criado_em")
        st = request.GET.get("status")
        mod = request.GET.get("modulo")
        if st:
            qs = qs.filter(status=st)
        if mod:
            qs = qs.filter(modulo_id=mod)
        paginator = Paginator(qs, 25)
        page = paginator.get_page(request.GET.get("page"))
        return render(request, "superadmin/artigos_list.html", {
            "menu_ativo": "artigos", "page_obj": page, "artigos": page,
            "modulos": ModuloEstudo.objects.filter(ativo=True).order_by("ordem"),
            "status_filter": st or "", "modulo_filter": mod or "",
        })


def _save_artigo(request, artigo=None):
    titulo = request.POST.get("titulo", "").strip()
    resumo = request.POST.get("resumo", "").strip()
    conteudo = request.POST.get("conteudo", "").strip()
    modulo_id = request.POST.get("modulo")
    status = request.POST.get("status", "draft")
    erros = []
    if not titulo:
        erros.append("O título é obrigatório.")
    if not modulo_id:
        erros.append("Selecione um módulo.")
    if not conteudo:
        erros.append("O conteúdo é obrigatório.")
    if erros:
        return erros, None
    if artigo is None:
        artigo = ArtigoEstudo()
    artigo.titulo = titulo
    artigo.resumo = resumo
    artigo.conteudo = conteudo
    artigo.modulo_id = int(modulo_id)
    artigo.status = status
    artigo.autor = request.POST.get("autor", "").strip() or "Redação NC Fly"
    artigo.seo_title = request.POST.get("seo_title", "").strip()
    artigo.meta_description = request.POST.get("meta_description", "").strip()
    artigo.imagem_url = request.POST.get("imagem_url", "").strip()
    try:
        artigo.tempo_leitura = int(request.POST.get("tempo_leitura") or 5)
    except (ValueError, TypeError):
        artigo.tempo_leitura = 5
    try:
        artigo.ordem = int(request.POST.get("ordem") or 0)
    except (ValueError, TypeError):
        artigo.ordem = 0
    if status == "published" and not artigo.publicado_em:
        artigo.publicado_em = timezone.now()
    img = request.FILES.get("imagem")
    if img:
        if img.content_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            return ["Formato de imagem não permitido."], None
        artigo.imagem = img
    artigo.save()
    return [], artigo


class ArtigoCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        return render(request, "superadmin/artigo_form.html", {
            "menu_ativo": "artigos", "modulos": ModuloEstudo.objects.filter(ativo=True).order_by("ordem"), "editando": False,
        })

    def post(self, request):
        erros, artigo = _save_artigo(request)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/artigo_form.html", {
                "menu_ativo": "artigos", "modulos": ModuloEstudo.objects.filter(ativo=True).order_by("ordem"),
                "editando": False, "form_data": request.POST,
            })
        messages.success(request, f'Artigo "{artigo.titulo}" criado.')
        return redirect(reverse("superadmin_artigo_edit", kwargs={"pk": artigo.pk}))


class ArtigoEditView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo.objects.select_related("modulo"), pk=pk)
        return render(request, "superadmin/artigo_form.html", {
            "menu_ativo": "artigos", "artigo": artigo, "videos": artigo.videos.order_by("ordem"),
            "modulos": ModuloEstudo.objects.filter(ativo=True).order_by("ordem"), "editando": True,
        })

    def post(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo, pk=pk)
        erros, artigo = _save_artigo(request, artigo)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/artigo_form.html", {
                "menu_ativo": "artigos", "artigo": artigo,
                "modulos": ModuloEstudo.objects.filter(ativo=True).order_by("ordem"),
                "editando": True, "form_data": request.POST,
            })
        messages.success(request, f'Artigo "{artigo.titulo}" atualizado.')
        return redirect(reverse("superadmin_artigo_edit", kwargs={"pk": artigo.pk}))


class ArtigoDeleteView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo.objects.select_related("modulo"), pk=pk)
        return render(request, "superadmin/artigo_confirma_delete.html", {"menu_ativo": "artigos", "artigo": artigo})

    def post(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo, pk=pk)
        titulo = artigo.titulo
        artigo.delete()
        messages.success(request, f'Artigo "{titulo}" excluído.')
        return redirect(reverse("superadmin_artigos_list"))


class ArtigoReviewIAView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo, pk=pk)
        try:
            from portal.services.prompts.artigo_estudo_review import review_artigo
            result = review_artigo(artigo.titulo, artigo.conteudo)

            # Aplica automaticamente os campos revisados no artigo
            fields_to_update = ["ia_revisao_json", "atualizado_em"]
            artigo.ia_revisao_json = result

            if result.get("titulo_revisado"):
                artigo.titulo = result["titulo_revisado"]
                fields_to_update.append("titulo")
            if result.get("resumo"):
                artigo.resumo = result["resumo"]
                fields_to_update.append("resumo")
            if result.get("conteudo_revisado"):
                artigo.conteudo = result["conteudo_revisado"]
                fields_to_update.append("conteudo")
            if result.get("seo_title"):
                artigo.seo_title = result["seo_title"]
                fields_to_update.append("seo_title")
            if result.get("meta_description"):
                artigo.meta_description = result["meta_description"]
                fields_to_update.append("meta_description")
            if result.get("keywords"):
                artigo.keywords_json = result["keywords"]
                fields_to_update.append("keywords_json")
            if result.get("youtube_search_terms"):
                artigo.youtube_search_terms_json = result["youtube_search_terms"]
                fields_to_update.append("youtube_search_terms_json")
            if result.get("tempo_leitura"):
                artigo.tempo_leitura = result["tempo_leitura"]
                fields_to_update.append("tempo_leitura")

            artigo.save(update_fields=fields_to_update)
            return JsonResponse({"ok": True, "result": result})
        except Exception as exc:
            logger.exception("Erro revisão IA artigo pk=%s", pk)
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)


class ArtigoBuscarVideosView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo, pk=pk)
        try:
            from portal.services.youtube_service import search_youtube_videos
            terms = artigo.youtube_search_terms_json or [artigo.titulo]
            all_v = []
            for t in terms[:3]:
                all_v.extend(search_youtube_videos(t, max_results=3))
            seen, unique = set(), []
            for v in all_v:
                if v["video_id"] not in seen:
                    seen.add(v["video_id"])
                    unique.append(v)
            saved = 0
            for i, v in enumerate(unique[:9]):
                _, created = ArtigoVideoYoutube.objects.update_or_create(
                    artigo=artigo, video_id=v["video_id"],
                    defaults={"titulo": v.get("titulo", "")[:300], "descricao": v.get("descricao", ""), "thumbnail_url": v.get("thumbnail_url", ""), "canal": v.get("canal", "")[:200], "duracao": v.get("duracao", ""), "visualizacoes": v.get("visualizacoes", 0), "termo_busca": v.get("termo_busca", "")[:200], "ordem": i, "ativo": True},
                )
                if created:
                    saved += 1
            data = list(artigo.videos.filter(ativo=True).order_by("ordem").values("id", "video_id", "titulo", "canal", "duracao", "thumbnail_url", "ativo"))
            return JsonResponse({"ok": True, "saved": saved, "total": len(data), "videos": data})
        except Exception as exc:
            logger.exception("Erro buscando vídeos artigo pk=%s", pk)
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)


# ---------------------------------------------------------------------------
# Módulos de Estudo — CRUD
# ---------------------------------------------------------------------------

class ModulosListView(SuperAdminRequiredMixin):
    def get(self, request):
        modulos = ModuloEstudo.objects.annotate(total_artigos=Count("artigos")).order_by("ordem", "titulo")
        return render(request, "superadmin/modulos_list.html", {"menu_ativo": "modulos", "modulos": modulos})


def _save_modulo(request, modulo=None):
    titulo = request.POST.get("titulo", "").strip()
    descricao = request.POST.get("descricao", "").strip()
    erros = []
    if not titulo:
        erros.append("O título é obrigatório.")
    if not descricao:
        erros.append("A descrição é obrigatória.")
    if erros:
        return erros, None
    if modulo is None:
        modulo = ModuloEstudo()
    modulo.titulo = titulo
    modulo.descricao = descricao
    modulo.icone = request.POST.get("icone", "").strip()
    modulo.cor = request.POST.get("cor", "#2563eb").strip()
    modulo.ativo = request.POST.get("ativo") == "on"
    try:
        modulo.ordem = int(request.POST.get("ordem") or 0)
    except (ValueError, TypeError):
        modulo.ordem = 0
    if not modulo.slug:
        from django.template.defaultfilters import slugify
        modulo.slug = slugify(titulo)
    modulo.save()
    return [], modulo


class ModuloCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        return render(request, "superadmin/modulo_form.html", {"menu_ativo": "modulos", "editando": False})

    def post(self, request):
        erros, modulo = _save_modulo(request)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/modulo_form.html", {"menu_ativo": "modulos", "editando": False, "form_data": request.POST})
        messages.success(request, f'Módulo "{modulo.titulo}" criado.')
        return redirect(reverse("superadmin_modulos_list"))


class ModuloEditView(SuperAdminRequiredMixin):
    def get(self, request, pk):
        modulo = get_object_or_404(ModuloEstudo, pk=pk)
        return render(request, "superadmin/modulo_form.html", {"menu_ativo": "modulos", "modulo": modulo, "editando": True})

    def post(self, request, pk):
        modulo = get_object_or_404(ModuloEstudo, pk=pk)
        erros, modulo = _save_modulo(request, modulo)
        if erros:
            for e in erros:
                messages.error(request, e)
            return render(request, "superadmin/modulo_form.html", {"menu_ativo": "modulos", "modulo": modulo, "editando": True, "form_data": request.POST})
        messages.success(request, f'Módulo "{modulo.titulo}" atualizado.')
        return redirect(reverse("superadmin_modulos_list"))
