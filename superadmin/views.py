"""
Views do painel superadmin NCfly.

Acesso restrito via SuperAdminRequiredMixin — somente pedro@ncfly.com.br.
URL base: /ncadm/
"""
import json
import logging
import re
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from gestao.models import Empresa
from django.http import JsonResponse
from portal.models import (
    NoticiaPublicada, JobExecucao, LeadPlataforma, LeadAlertaEmail,
    ModuloEstudo, ArtigoEstudo, ArtigoVideoYoutube, PortalUser,
    ComentarioArtigo,
)
from portal.views import invalidate_news_cache

from .mixins import SuperAdminRequiredMixin

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class DashboardView(SuperAdminRequiredMixin):
    def get(self, request):
        from .services.dashboard import build_dashboard_context
        context = build_dashboard_context()
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
        invalidate_news_cache()
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
        context = {"menu_ativo": "upload"}
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
                "menu_ativo": "upload",
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


def _normalizar_digitos(valor: str) -> str:
    """Remove qualquer caractere nao numerico. Util para CNPJ/CPF/CEP."""
    return re.sub(r"\D", "", valor or "")


def _formatar_cep(cep_digits: str) -> str:
    """Formata 8 digitos como 00000-000. Se nao tiver 8 digitos, retorna como veio."""
    if len(cep_digits) == 8:
        return f"{cep_digits[:5]}-{cep_digits[5:]}"
    return cep_digits


def _formatar_cnpj(cnpj_digits: str) -> str:
    """Formata 14 digitos como 00.000.000/0000-00."""
    if len(cnpj_digits) == 14:
        return f"{cnpj_digits[:2]}.{cnpj_digits[2:5]}.{cnpj_digits[5:8]}/{cnpj_digits[8:12]}-{cnpj_digits[12:]}"
    return cnpj_digits


def _extrair_dados_empresa(post):
    """Le todos os campos do formulario de empresa e normaliza mascaras.

    Retorna (dados_dict, erros_list). Usado tanto em create quanto em edit.
    """
    nome = post.get("nome", "").strip()
    razao_social = post.get("razao_social", "").strip()
    tipo_pessoa = post.get("tipo_pessoa", "PJ").strip() or "PJ"
    cnpj_raw = post.get("cnpj", "").strip()
    documento_titular = post.get("documento_titular", "").strip()
    responsavel_nome = post.get("responsavel_nome", "").strip()
    email_contato = post.get("email_contato", "").strip()
    telefone_contato = post.get("telefone_contato", "").strip()
    whatsapp = post.get("whatsapp", "").strip()
    website = post.get("website", "").strip()
    cep_raw = post.get("cep", "").strip()
    endereco = post.get("endereco", "").strip()
    numero = post.get("numero", "").strip()
    complemento = post.get("complemento", "").strip()
    bairro = post.get("bairro", "").strip()
    cidade = post.get("cidade", "").strip()
    estado = post.get("estado", "").strip()
    descricao_rodape = post.get("descricao_rodape", "").strip()
    limite_colaboradores_raw = post.get("limite_colaboradores", "0").strip()
    ativo = post.get("ativo") == "1"

    erros = []

    # CNPJ — normaliza e valida tamanho (se informado)
    cnpj = ""
    if cnpj_raw:
        cnpj_digits = _normalizar_digitos(cnpj_raw)
        if len(cnpj_digits) != 14:
            erros.append("CNPJ deve ter 14 digitos.")
        else:
            cnpj = _formatar_cnpj(cnpj_digits)

    # CEP — normaliza e valida (se informado)
    cep = ""
    if cep_raw:
        cep_digits = _normalizar_digitos(cep_raw)
        if len(cep_digits) != 8:
            erros.append("CEP deve ter 8 digitos.")
        else:
            cep = _formatar_cep(cep_digits)

    # Tipo de pessoa limitado aos valores validos
    if tipo_pessoa not in ("PJ", "PF"):
        tipo_pessoa = "PJ"

    # UF: 2 letras maiusculas (se informado)
    if estado:
        estado_limpo = re.sub(r"[^A-Za-z]", "", estado).upper()[:2]
        estado = estado_limpo

    # Limite colaboradores
    try:
        limite_colaboradores = int(limite_colaboradores_raw)
        if limite_colaboradores < 0:
            limite_colaboradores = 0
    except (ValueError, TypeError):
        limite_colaboradores = 0

    dados = {
        "nome": nome,
        "razao_social": razao_social,
        "tipo_pessoa": tipo_pessoa,
        "cnpj": cnpj or None,  # null permitido no model (unique)
        "documento_titular": documento_titular,
        "responsavel_nome": responsavel_nome,
        "email_contato": email_contato,
        "telefone_contato": telefone_contato,
        "whatsapp": whatsapp,
        "website": website,
        "cep": cep,
        "endereco": endereco,
        "numero": numero,
        "complemento": complemento,
        "bairro": bairro,
        "cidade": cidade,
        "estado": estado,
        "descricao_rodape": descricao_rodape,
        "limite_colaboradores": limite_colaboradores,
        "ativo": ativo,
    }
    return dados, erros


class EmpresaCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        context = {"menu_ativo": "empresas", "editando": False, "form_data": {}}
        return render(request, "superadmin/empresa_form.html", context)

    def post(self, request):
        dados, erros = _extrair_dados_empresa(request.POST)

        if not dados["nome"]:
            erros.append("Nome da empresa e obrigatorio.")
        if dados["nome"] and Empresa.objects.filter(nome=dados["nome"]).exists():
            erros.append(f'Ja existe uma empresa com o nome "{dados["nome"]}".')
        if dados["cnpj"] and Empresa.objects.filter(cnpj=dados["cnpj"]).exists():
            erros.append(f'Ja existe uma empresa com o CNPJ "{dados["cnpj"]}".')

        if erros:
            for erro in erros:
                messages.error(request, erro)
            context = {
                "menu_ativo": "empresas",
                "editando": False,
                "form_data": request.POST,
            }
            return render(request, "superadmin/empresa_form.html", context)

        empresa = Empresa.objects.create(**dados)

        logger.info(
            "Superadmin criou empresa pk=%s nome=%r user=%s",
            empresa.pk,
            dados["nome"],
            request.user.email,
        )
        messages.success(request, f'Empresa "{dados["nome"]}" criada com sucesso.')
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
        dados, erros = _extrair_dados_empresa(request.POST)

        if not dados["nome"]:
            erros.append("Nome da empresa e obrigatorio.")
        if dados["nome"] and Empresa.objects.filter(nome=dados["nome"]).exclude(pk=pk).exists():
            erros.append(f'Ja existe outra empresa com o nome "{dados["nome"]}".')
        if dados["cnpj"] and Empresa.objects.filter(cnpj=dados["cnpj"]).exclude(pk=pk).exists():
            erros.append(f'Ja existe outra empresa com o CNPJ "{dados["cnpj"]}".')

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

        for campo, valor in dados.items():
            setattr(empresa, campo, valor)
        empresa.save()

        logger.info(
            "Superadmin editou empresa pk=%s nome=%r user=%s",
            empresa.pk,
            dados["nome"],
            request.user.email,
        )
        messages.success(request, f'Empresa "{dados["nome"]}" atualizada.')
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
    _persistir_videos_preview(request, artigo)
    return [], artigo


def _persistir_videos_preview(request, artigo):
    payload = (request.POST.get("videos_preview_json") or "").strip()
    if not payload:
        return
    try:
        videos = json.loads(payload)
    except (ValueError, TypeError):
        return
    if not isinstance(videos, list):
        return
    from django.db.models import Max
    base_ordem = artigo.videos.aggregate(m=Max("ordem")).get("m") or 0
    for i, v in enumerate(videos[:9]):
        if not isinstance(v, dict):
            continue
        video_id = (v.get("video_id") or "").strip()
        if not video_id:
            continue
        ArtigoVideoYoutube.objects.update_or_create(
            artigo=artigo, video_id=video_id,
            defaults={
                "titulo": (v.get("titulo") or "")[:300],
                "descricao": v.get("descricao", "") or "",
                "thumbnail_url": v.get("thumbnail_url", "") or "",
                "canal": (v.get("canal") or "")[:200],
                "duracao": v.get("duracao", "") or "",
                "visualizacoes": v.get("visualizacoes", 0) or 0,
                "termo_busca": (v.get("termo_busca") or "preview")[:200],
                "ordem": base_ordem + i + 1,
                "ativo": True,
            },
        )


class ArtigoCreateView(SuperAdminRequiredMixin):
    def get(self, request):
        return render(request, "superadmin/artigo_form.html", {
            "menu_ativo": "artigos",
            "modulos": ModuloEstudo.objects.filter(ativo=True).order_by("ordem"),
            "editando": False,
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
        messages.success(request, f'Artigo "{artigo.titulo}" criado. Agora voce pode revisar com IA e buscar videos.')
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


class ArtigoGerarCompletoIAView(SuperAdminRequiredMixin):
    """Gera artigo completo via IA a partir de briefing curto (preview — nao salva)."""

    def post(self, request):
        briefing = (request.POST.get("briefing") or "").strip()
        if len(briefing) < 30:
            return JsonResponse(
                {"ok": False, "error": "Briefing muito curto (mínimo 30 caracteres)."},
                status=400,
            )
        try:
            from portal.services.prompts.artigo_gerar_completo import gerar_artigo_completo
            result = gerar_artigo_completo(briefing)
            return JsonResponse({"ok": True, "result": result})
        except ValueError as exc:
            return JsonResponse({"ok": False, "error": str(exc)}, status=400)
        except Exception as exc:
            logger.exception("Erro gerar artigo IA (briefing len=%s)", len(briefing))
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)


class ArtigoRevisarIAPreviewView(SuperAdminRequiredMixin):
    """Revisao IA sobre titulo/conteudo do form (sem PK, sem persistir)."""

    def post(self, request):
        titulo = (request.POST.get("titulo") or "").strip()
        conteudo = (request.POST.get("conteudo") or "").strip()
        if len(titulo) < 5 or len(conteudo) < 50:
            return JsonResponse(
                {"ok": False, "error": "Preencha titulo (>=5 chars) e conteudo (>=50 chars) antes de revisar."},
                status=400,
            )
        try:
            from portal.services.prompts.artigo_estudo_review import review_artigo
            result = review_artigo(titulo, conteudo)
            return JsonResponse({"ok": True, "result": result})
        except Exception as exc:
            logger.exception("Erro revisao IA preview")
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)


class ArtigoBuscarVideosPreviewView(SuperAdminRequiredMixin):
    """Busca preview de videos no YouTube (sem PK, sem persistir)."""

    def post(self, request):
        keyword = (request.POST.get("keyword") or "").strip()
        if not keyword:
            return JsonResponse(
                {"ok": False, "error": "Informe uma palavra-chave para buscar."}, status=400
            )
        try:
            from portal.services.youtube_service import search_youtube_videos
            videos = search_youtube_videos(keyword, max_results=9) or []
            seen, unique = set(), []
            for v in videos:
                vid = v.get("video_id")
                if vid and vid not in seen:
                    seen.add(vid)
                    unique.append({
                        "video_id": vid,
                        "titulo": v.get("titulo", ""),
                        "descricao": v.get("descricao", ""),
                        "thumbnail_url": v.get("thumbnail_url", ""),
                        "canal": v.get("canal", ""),
                        "duracao": v.get("duracao", ""),
                        "visualizacoes": v.get("visualizacoes", 0),
                        "termo_busca": keyword,
                    })
            return JsonResponse({"ok": True, "videos": unique[:9]})
        except Exception as exc:
            logger.exception("Erro buscar videos preview keyword=%r", keyword)
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)


class ArtigoAdicionarVideoUrlView(SuperAdminRequiredMixin):
    """Adiciona manualmente um video do YouTube ao artigo a partir de URL/ID."""

    def post(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo, pk=pk)
        url_raw = (request.POST.get("url") or "").strip()
        if not url_raw:
            return JsonResponse(
                {"ok": False, "error": "Informe a URL ou ID do vídeo."}, status=400
            )

        try:
            from portal.services.youtube_service import extract_video_id, fetch_videos_by_ids

            video_id = extract_video_id(url_raw)
            if not video_id:
                return JsonResponse(
                    {"ok": False, "error": "URL inválida — não foi possível extrair o ID do vídeo."},
                    status=400,
                )

            videos = fetch_videos_by_ids([video_id])
            if not videos:
                return JsonResponse(
                    {"ok": False, "error": "Não foi possível obter metadados do vídeo no YouTube."},
                    status=502,
                )
            v = videos[0]

            from django.db.models import Max

            max_ordem = artigo.videos.aggregate(m=Max("ordem")).get("m") or 0
            obj, created = ArtigoVideoYoutube.objects.update_or_create(
                artigo=artigo,
                video_id=v["video_id"],
                defaults={
                    "titulo": (v.get("titulo") or "")[:300],
                    "descricao": v.get("descricao", "") or "",
                    "thumbnail_url": v.get("thumbnail_url", "") or "",
                    "canal": (v.get("canal") or "")[:200],
                    "duracao": v.get("duracao", "") or "",
                    "visualizacoes": v.get("visualizacoes", 0) or 0,
                    "termo_busca": (v.get("termo_busca") or "manual")[:200],
                    "ordem": max_ordem + 1,
                    "ativo": True,
                },
            )
            return JsonResponse({
                "ok": True,
                "created": created,
                "video": {
                    "id": obj.id,
                    "video_id": obj.video_id,
                    "titulo": obj.titulo,
                    "canal": obj.canal,
                    "duracao": obj.duracao,
                    "thumbnail_url": obj.thumbnail_url,
                    "visualizacoes": obj.visualizacoes,
                    "ativo": obj.ativo,
                    "ordem": obj.ordem,
                    "url": obj.youtube_url,
                },
            })
        except Exception as exc:
            logger.exception("Erro adicionando vídeo por URL artigo pk=%s", pk)
            return JsonResponse({"ok": False, "error": str(exc)}, status=500)


class ArtigoBuscarVideosView(SuperAdminRequiredMixin):
    def post(self, request, pk):
        artigo = get_object_or_404(ArtigoEstudo, pk=pk)
        try:
            from portal.services.youtube_service import search_youtube_videos
            keyword = (request.POST.get("keyword") or "").strip()
            if keyword:
                # palavra-chave manual tem prioridade; busca mais resultados
                terms = [keyword]
            else:
                terms = artigo.youtube_search_terms_json or [artigo.titulo]
            all_v = []
            per_term = 9 if keyword else 3
            for t in terms[:3]:
                all_v.extend(search_youtube_videos(t, max_results=per_term))
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


class ModuloDeleteView(SuperAdminRequiredMixin):
    """
    GET  -> pagina de confirmacao (mostra quantos artigos serao cascateados)
    POST -> hard delete do modulo
    """

    def get(self, request, pk):
        modulo = get_object_or_404(
            ModuloEstudo.objects.annotate(total_artigos=Count("artigos")),
            pk=pk,
        )
        return render(
            request,
            "superadmin/modulo_confirma_delete.html",
            {"menu_ativo": "modulos", "modulo": modulo},
        )

    def post(self, request, pk):
        modulo = get_object_or_404(ModuloEstudo, pk=pk)
        titulo = modulo.titulo
        total_artigos = modulo.artigos.count()
        modulo.delete()
        logger.info(
            "Superadmin excluiu modulo pk=%s titulo=%r artigos_cascateados=%s user=%s",
            pk,
            titulo,
            total_artigos,
            request.user.email,
        )
        if total_artigos:
            messages.success(
                request,
                f'Módulo "{titulo}" excluído ({total_artigos} artigo(s) removido(s) em cascata).',
            )
        else:
            messages.success(request, f'Módulo "{titulo}" excluído.')
        return redirect(reverse("superadmin_modulos_list"))
