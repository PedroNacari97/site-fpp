from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.contrib import messages
from django.urls import reverse
from decimal import Decimal
from gestao.models import ContaFidelidade, Movimentacao, AcessoClienteLog
from django.db import models, transaction

from ..forms import (
    ContaFidelidadeForm,
    ProgramaFidelidadeForm,
    ClienteForm,
    NovoClienteForm,
    AeroportoForm,
    EmissaoPassagemForm,
    EmissaoHotelForm,
    CotacaoVooForm,
    AcompanhamentoPassagemForm,
)
from django.contrib.auth.models import User
from ..models import (
    Cliente,
    ContaFidelidade,
    ProgramaFidelidade,
    EmissaoPassagem,
    Aeroporto,
    ValorMilheiro,
    EmissaoHotel,
    CotacaoVoo,
    Passageiro,
    PassageiroFrequente,
    Escala,
    CompanhiaAerea,
    AcompanhamentoPassagem,
)
import csv
import json
from datetime import timedelta

from .permissions import require_admin_or_operator, scope_queryset_to_company
from gestao.services.emissao_financeiro import (
    calcular_custo_milhas,
    calcular_custo_total_emissao,
    calcular_economia,
    calcular_lucro_emissao,
    registrar_movimentacao_pontos,
)
from gestao.services.clientes_programas import (
    build_clientes_programas_map,
    build_contas_administradas_programas_map,
    build_empresa_programas_map,
)
from gestao.services.cpf_limite import get_cpf_control_data, registrar_uso_cpfs, validar_limite_cpfs
from gestao.utils import parse_br_date, validate_cpf_digits
from gestao.services.dashboard import (
    _current_management_filters,
    _management_filter_list,
    _management_filter_value,
    build_operational_dashboard_context,
)
from gestao.services.emissao_preview import build_emissao_preview_context
from gestao.services.acompanhamento_passagem import (
    ensure_acompanhamento_passagem,
    sync_acompanhamento_passagem,
)
from services.pdf_service import emissao_pdf_response




def _get_emissao_for_preview(request, emissao_id):
    return get_object_or_404(
        scope_queryset_to_company(
            EmissaoPassagem.objects.select_related(
                "cliente__usuario",
                "conta_administrada",
                "programa",
                "emissor_parceiro",
                "companhia_aerea",
                "aeroporto_partida",
                "aeroporto_destino",
            ).prefetch_related("passageiros", "escalas__aeroporto"),
            request,
            "cliente__empresa",
            "conta_administrada__empresa",
            "emissor_parceiro__empresa",
        ),
        id=emissao_id,
    )


def _build_emissao_template_context(*, form, empresa, cliente_id=None, emissoes=None, passageiros_json="[]", escalas_por_tipo=None, aeroportos=None, menu_ativo="emissoes", cotacao_conversion=None):
    escalas_por_tipo = escalas_por_tipo or {"ida": [], "volta": []}
    aeroportos = aeroportos or list(Aeroporto.objects.values("id", "nome", "sigla"))
    cliente_programas = build_clientes_programas_map(empresa_id=getattr(empresa, "id", None))
    contas_adm_programas = build_contas_administradas_programas_map(empresa_id=getattr(empresa, "id", None))
    empresa_programas = build_empresa_programas_map(empresa_id=getattr(empresa, "id", None))
    conta = None
    tipo = getattr(form.instance, 'emissor_parceiro_id', None) and 'parceiro' or ('administrada' if getattr(form.instance, 'conta_administrada_id', None) else 'cliente')
    if form.is_bound:
        tipo = form.data.get('tipo_emissao') or tipo
        programa_id = form.data.get('programa')
        cliente_sel = form.data.get('cliente')
        conta_adm_sel = form.data.get('conta_administrada')
    else:
        programa_id = getattr(form.instance, 'programa_id', None) or form.initial.get('programa')
        cliente_sel = getattr(form.instance, 'cliente_id', None) or form.initial.get('cliente')
        conta_adm_sel = getattr(form.instance, 'conta_administrada_id', None) or form.initial.get('conta_administrada')
    if programa_id:
        filtros = {'programa_id': programa_id}
        if tipo == 'administrada' and conta_adm_sel:
            filtros['conta_administrada_id'] = conta_adm_sel
        elif tipo == 'cliente' and cliente_sel:
            filtros['cliente_id'] = cliente_sel
        if len(filtros) > 1:
            conta = ContaFidelidade.objects.filter(**filtros).select_related('programa', 'cliente__usuario', 'conta_administrada').first()
    controle = get_cpf_control_data(conta)
    clientes_ids = set(cliente_programas.keys())
    if cliente_sel:
        try:
            clientes_ids.add(int(cliente_sel))
        except (TypeError, ValueError):
            pass
    cliente_context_url_template = reverse("admin_emissao_cliente_contexto", args=[0]).replace("/0/", "/__ID__/")
    passageiro_frequente_url_template = reverse("admin_emissao_passageiro_frequente_detalhe", args=[0]).replace("/0/", "/__ID__/")
    return {
        'form': form,
        'emissoes': emissoes if emissoes is not None else EmissaoPassagem.objects.all().order_by('-data_ida'),
        'passageiros_json': passageiros_json,
        'escalas_ida_json': json.dumps(escalas_por_tipo['ida']),
        'escalas_volta_json': json.dumps(escalas_por_tipo['volta']),
        'aeroportos_json': json.dumps(aeroportos),
        'cliente_id': cliente_id,
        'cliente_programas_json': json.dumps(cliente_programas),
        'contas_adm_programas_json': json.dumps(contas_adm_programas),
        'empresa_programas_json': json.dumps(empresa_programas),
        'cpf_controle_json': json.dumps(controle or {}),
        'cliente_context_url_template': cliente_context_url_template,
        'passageiro_frequente_url_template': passageiro_frequente_url_template,
        'cotacao_conversion': cotacao_conversion,
        'cotacao_conversion_id': cotacao_conversion["id"] if cotacao_conversion else None,
        'menu_ativo': menu_ativo,
    }


def _mask_cpf(value):
    digits = "".join(ch for ch in str(value or "") if ch.isdigit())
    if len(digits) != 11:
        return ""
    return f"{digits[:3]}.***.***-{digits[-2:]}"


@login_required
def emissao_cliente_contexto(request, cliente_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cliente = get_object_or_404(
        scope_queryset_to_company(
            Cliente.objects.select_related("usuario"),
            request,
            "empresa",
        ),
        id=cliente_id,
        perfil="cliente",
        ativo=True,
    )
    passageiros = PassageiroFrequente.objects.filter(cliente=cliente).order_by("nome")
    cliente_nome = cliente.usuario.get_full_name() or cliente.usuario.username
    cliente_cpf = cliente.cpf or ""
    titular_entry = {
        "id": f"titular_{cliente.id}",
        "nome": cliente_nome,
        "cpf": cliente_cpf,
        "cpf_masked": _mask_cpf(cliente_cpf),
        "rg": "",
        "passaporte": "",
        "passaporte_validade": "",
        "data_nascimento": cliente.data_nascimento.isoformat() if getattr(cliente, "data_nascimento", None) else "",
        "is_titular": True,
    }
    passageiros_list = [titular_entry] + [
        {
            "id": item.id,
            "nome": item.nome,
            "cpf_masked": _mask_cpf(item.cpf),
            "is_titular": False,
        }
        for item in passageiros
    ]
    return JsonResponse(
        {
            "cliente": {
                "id": cliente.id,
                "nome": cliente_nome,
                "cpf": cliente_cpf,
            },
            "passageiros_frequentes": passageiros_list,
        }
    )


@login_required
def emissao_passageiro_frequente_detalhe(request, passageiro_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    passageiro = get_object_or_404(
        scope_queryset_to_company(
            PassageiroFrequente.objects.select_related("cliente"),
            request,
            "cliente__empresa",
        ),
        id=passageiro_id,
    )
    return JsonResponse(
        {
            "id": passageiro.id,
            "nome": passageiro.nome or "",
            "cpf": passageiro.cpf or "",
            "rg": passageiro.rg or "",
            "passaporte": passageiro.passaporte or "",
            "passaporte_validade": passageiro.passaporte_validade.isoformat() if passageiro.passaporte_validade else "",
            "data_nascimento": passageiro.data_nascimento.isoformat() if passageiro.data_nascimento else "",
        }
    )

def _build_escalas_from_request(request):
    escalas = []
    for tipo in ("ida", "volta"):
        if not request.POST.get(f"{tipo}_tem_escala"):
            continue
        try:
            total_escalas = int(request.POST.get(f"total_escalas_{tipo}", 0) or 0)
        except (TypeError, ValueError):
            total_escalas = 0
        for i in range(total_escalas):
            aeroporto_id = request.POST.get(f"escala-{tipo}-{i}-aeroporto")
            dur = request.POST.get(f"escala-{tipo}-{i}-duracao")
            cidade = request.POST.get(f"escala-{tipo}-{i}-cidade")
            if aeroporto_id and dur:
                try:
                    h, m = map(int, dur.split(":"))
                except (TypeError, ValueError):
                    continue
                escalas.append(
                    {
                        "aeroporto_id": aeroporto_id,
                        "duracao": timedelta(hours=h, minutes=m),
                        "cidade": cidade or "",
                        "tipo": tipo,
                        "ordem": i + 1,
                    }
                )
    return escalas


def _format_escalas(escalas_queryset):
    escalas_por_tipo = {"ida": [], "volta": []}
    for e in escalas_queryset:
        total_seconds = int(e["duracao"].total_seconds())
        h = total_seconds // 3600
        m = (total_seconds % 3600) // 60
        escala_formatada = {
            "aeroporto_id": e["aeroporto_id"],
            "duracao": f"{h:02d}:{m:02d}",
            "cidade": e["cidade"],
            "ordem": e.get("ordem") or 0,
        }
        escalas_por_tipo.get(e.get("tipo") or "ida", escalas_por_tipo["ida"]).append(
            escala_formatada
        )
    for tipo in escalas_por_tipo:
        escalas_por_tipo[tipo] = sorted(
            escalas_por_tipo[tipo], key=lambda esc: esc.get("ordem") or 0
        )
    return escalas_por_tipo


def _serialize_passageiros_list(passageiros):
    for row in passageiros:
        for field in ("passaporte_validade", "data_nascimento"):
            if row.get(field) and hasattr(row[field], "isoformat"):
                row[field] = row[field].isoformat()
    return passageiros


def _parse_passageiros(post_data):
    passageiros = []
    try:
        total = int(post_data.get("total_passageiros", 0))
    except (TypeError, ValueError):
        total = 0
    for i in range(total):
        nome = post_data.get(f"passageiro-{i}-nome")
        cpf = post_data.get(f"passageiro-{i}-cpf")
        rg = post_data.get(f"passageiro-{i}-rg")
        passaporte = post_data.get(f"passageiro-{i}-passaporte")
        passaporte_validade = post_data.get(f"passageiro-{i}-passaporte-validade")
        data_nascimento = post_data.get(f"passageiro-{i}-data-nascimento")
        observacoes = post_data.get(f"passageiro-{i}-observacoes")
        categoria = post_data.get(f"passageiro-{i}-categoria")

        passageiros.append(
            {
                "nome": nome,
                "cpf": cpf,
                "rg": rg,
                "passaporte": passaporte,
                "passaporte_validade": passaporte_validade,
                "data_nascimento": data_nascimento,
                "observacoes": observacoes,
                "categoria": categoria,
            }
        )
    return passageiros


def _validate_passageiros(passageiros):
    from datetime import date

    errors = []
    for idx, passageiro in enumerate(passageiros, start=1):
        nome = (passageiro.get("nome") or "").strip()
        cpf = passageiro.get("cpf")
        categoria = passageiro.get("categoria")
        passaporte = (passageiro.get("passaporte") or "").strip()
        passaporte_validade_raw = passageiro.get("passaporte_validade")

        if not nome:
            errors.append(f"Passageiro {idx}: informe o nome.")
        normalized_cpf = None
        try:
            normalized_cpf = validate_cpf_digits(
                cpf or "", field_label=f"CPF do passageiro {idx}"
            )
        except ValidationError as exc:
            errors.append(str(exc.message))
        if not categoria:
            errors.append(f"Passageiro {idx}: informe a categoria.")

        passaporte_validade = None
        if passaporte_validade_raw:
            try:
                passaporte_validade = parse_br_date(
                    passaporte_validade_raw, field_label=f"Validade do passaporte do passageiro {idx}"
                )
            except ValidationError as exc:
                errors.append(str(exc.message))
        if passaporte:
            if not passaporte_validade:
                errors.append(
                    f"Passageiro {idx}: validade do passaporte é obrigatória quando o passaporte é informado."
                )
            elif passaporte_validade < date.today():
                errors.append(
                    f"Passageiro {idx}: validade do passaporte não pode estar no passado."
                )
        passageiro["passaporte_validade"] = passaporte_validade
        try:
            passageiro["data_nascimento"] = parse_br_date(
                passageiro.get("data_nascimento"),
                field_label=f"Data de nascimento do passageiro {idx}",
            )
        except ValidationError as exc:
            errors.append(str(exc.message))
            passageiro["data_nascimento"] = None
        if not passageiro.get("data_nascimento"):
            errors.append(f"Passageiro {idx}: data de nascimento é obrigatória.")
        passageiro["cpf"] = normalized_cpf
        passageiro["nome"] = nome
        passageiro["passaporte"] = passaporte
        passageiro["rg"] = (passageiro.get("rg") or "").strip()
        passageiro["observacoes"] = (passageiro.get("observacoes") or "").strip()
    return errors


def _build_passageiros_json_for_context(post_data):
    return json.dumps(_serialize_passageiros_list(_parse_passageiros(post_data)))


def _resolve_cotacao_for_conversion(request):
    cotacao_id = request.GET.get("cotacao_id") or request.POST.get("cotacao_id")
    if not cotacao_id:
        return None
    return get_object_or_404(
        scope_queryset_to_company(
            CotacaoVoo.objects.select_related(
                "cliente__usuario",
                "conta_administrada",
                "programa",
                "origem",
                "destino",
                "emissao",
            ),
            request,
            "cliente__empresa",
            "conta_administrada__empresa",
        ),
        id=cotacao_id,
    )


def _build_emissao_initial_from_cotacao(cotacao):
    companhia = None
    companhia_nome = (cotacao.companhia_aerea or "").strip()
    if companhia_nome:
        companhia = CompanhiaAerea.objects.filter(nome__iexact=companhia_nome).first()

    detalhes_parts = []
    observacoes = (cotacao.observacoes or "").strip()
    if observacoes:
        detalhes_parts.append(observacoes)
    classe = (cotacao.classe or "").strip()
    if classe:
        detalhes_parts.append(f"Classe cotada: {classe}")

    valor_referencia_pontos = None
    if cotacao.milhas and cotacao.valor_milheiro not in (None, ""):
        valor_referencia_pontos = calcular_custo_milhas(
            cotacao.milhas,
            cotacao.valor_milheiro,
        )

    return {
        "tipo_emissao": "administrada" if cotacao.conta_administrada_id else "cliente",
        "cliente": cotacao.cliente_id,
        "conta_administrada": cotacao.conta_administrada_id,
        "programa": cotacao.programa_id,
        "companhia_aerea": companhia.id if companhia else "",
        "aeroporto_partida": cotacao.origem_id,
        "aeroporto_destino": cotacao.destino_id,
        "data_ida": cotacao.data_ida.strftime("%Y-%m-%dT%H:%M") if cotacao.data_ida else "",
        "data_volta": cotacao.data_volta.strftime("%Y-%m-%dT%H:%M") if cotacao.data_volta else "",
        "qtd_adultos": cotacao.qtd_passageiros or 1,
        "qtd_criancas": 0,
        "qtd_bebes": 0,
        "valor_referencia": cotacao.valor_referencia_manual if cotacao.valor_referencia_manual not in (None, "") else cotacao.valor_passagem,
        "valor_taxas": cotacao.taxas,
        "pontos_utilizados": cotacao.milhas,
        "valor_referencia_pontos": valor_referencia_pontos,
        "economia_obtida": cotacao.economia,
        "detalhes": "\n\n".join(detalhes_parts),
        "valor_milheiro_parceiro": cotacao.valor_milheiro,
        "valor_venda_final": cotacao.valor_vista,
        "valor_total_final": cotacao.valor_parcelado,
        "milhas_do_cliente": not bool(cotacao.conta_administrada_id),
    }


def _build_cotacao_conversion_context(cotacao):
    companhia_nome = (cotacao.companhia_aerea or "").strip()
    companhia_resolvida = False
    if companhia_nome:
        companhia_resolvida = CompanhiaAerea.objects.filter(nome__iexact=companhia_nome).exists()

    faltantes = [
        "Localizador da reserva.",
        f"Distribuicao dos {cotacao.qtd_passageiros or 0} passageiro(s) entre adultos, criancas e bebes.",
        "Dados completos dos passageiros que vao viajar.",
    ]
    if companhia_nome and not companhia_resolvida:
        faltantes.insert(0, f'Selecionar a companhia aerea cadastrada correspondente a "{companhia_nome}".')
    elif not companhia_nome:
        faltantes.insert(0, "Selecionar a companhia aerea da emissao.")

    return {
        "id": cotacao.id,
        "cliente_nome": (
            cotacao.cliente.usuario.get_full_name()
            or cotacao.cliente.usuario.username
            or str(cotacao.cliente)
        ),
        "trecho": f"{cotacao.origem or '-'} -> {cotacao.destino or '-'}",
        "faltantes": faltantes,
    }


def _render_nova_emissao_form(
    request,
    *,
    form,
    empresa,
    cliente_id=None,
    passageiros_json="[]",
    escalas_por_tipo=None,
    cotacao_conversion=None,
):
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        _build_emissao_template_context(
            form=form,
            empresa=empresa,
            cliente_id=cliente_id,
            emissoes=EmissaoPassagem.objects.all().order_by("-data_ida"),
            passageiros_json=passageiros_json,
            escalas_por_tipo=escalas_por_tipo,
            cotacao_conversion=cotacao_conversion,
        ),
    )


# --- EMISSÕES ---
@login_required
def admin_emissoes(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    management_context = build_operational_dashboard_context(user=request.user, request=request)
    management_dashboard = management_context["management_dashboard"]
    active_filters = _current_management_filters(request)
    start_date = _management_filter_value(active_filters, "data_inicio")
    end_date = _management_filter_value(active_filters, "data_fim")
    selected_clientes = _management_filter_list(active_filters, "cliente")
    selected_emissores = _management_filter_list(active_filters, "emissor")
    selected_programas = _management_filter_list(active_filters, "programa")
    selected_contas = _management_filter_list(active_filters, "conta")
    selected_status = _management_filter_value(active_filters, "status")

    emissoes = scope_queryset_to_company(
        EmissaoPassagem.objects.filter(
            Q(cliente__perfil="cliente", cliente__ativo=True) | Q(conta_administrada__isnull=False)
        ).select_related(
            "cliente",
            "programa",
            "aeroporto_partida",
            "aeroporto_destino",
            "conta_administrada",
            "emissor_parceiro",
            "companhia_aerea",
        ),
        request,
        "cliente__empresa",
        "conta_administrada__empresa",
        "emissor_parceiro__empresa",
    )
    if start_date:
        emissoes = emissoes.filter(criado_em__date__gte=start_date)
    if end_date:
        emissoes = emissoes.filter(criado_em__date__lte=end_date)
    if selected_clientes:
        emissoes = emissoes.filter(cliente_id__in=selected_clientes)
    if selected_emissores:
        emissoes = emissoes.filter(emissor_parceiro_id__in=selected_emissores)
    if selected_programas:
        emissoes = emissoes.filter(programa_id__in=selected_programas)
    if selected_contas:
        emissoes = emissoes.filter(conta_administrada_id__in=selected_contas)
    if selected_status == "emitido":
        emissoes = emissoes.exclude(localizador="").exclude(localizador__isnull=True)
    elif selected_status == "pendente":
        emissoes = emissoes.filter(Q(localizador="") | Q(localizador__isnull=True))
    emissoes = emissoes.order_by("-criado_em")

    if request.GET.get("export") == "excel":
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="emissoes.csv"'
        writer = csv.writer(response)
        writer.writerow(
            [
                "Cliente",
                "Programa",
                "Aeroporto Partida",
                "Aeroporto Destino",
                "Data Ida",
                "Data Volta",
                "Qtd Passageiros",
                "Valor Referência",
                "Taxas",
                "Pontos Usados",
                "Economia",
                "Detalhes",
            ]
        )
        for e in emissoes:
            writer.writerow(
                [
                    str(e.cliente),
                    str(e.programa),
                    e.aeroporto_partida,
                    e.aeroporto_destino,
                    e.data_ida,
                    e.data_volta,
                    e.qtd_passageiros,
                    e.valor_referencia,
                    e.valor_taxas,
                    e.pontos_utilizados,
                    e.economia_obtida,
                    e.detalhes,
                ]
            )
        return response

    total_emissoes = emissoes.count()
    total_receita = sum(float(item.valor_total_final or item.valor_venda_final or 0) for item in emissoes)
    total_custo = sum(float(item.custo_total or 0) for item in emissoes)
    total_lucro = sum(float(item.lucro or 0) for item in emissoes)
    return render(
        request,
        "admin_custom/emissoes.html",
        {
            "emissoes": emissoes,
            "management_dashboard": management_dashboard,
            "emissao_totais": {
                "total": total_emissoes,
                "receita": f"R$ {total_receita:,.2f}",
                "custo": f"R$ {total_custo:,.2f}",
                "lucro": f"R$ {total_lucro:,.2f}",
            },
            "menu_ativo": "emissoes",
        },
    )


@login_required
def nova_emissao(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cliente_id = request.GET.get("cliente_id")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    cotacao = _resolve_cotacao_for_conversion(request)
    cotacao_conversion = _build_cotacao_conversion_context(cotacao) if cotacao else None
    if cotacao and cotacao.status != "emissao":
        messages.error(
            request,
            "Mude a cotacao para Emitido antes de concluir a emissao operada.",
        )
        return redirect("admin_editar_cotacao_voo", cotacao.id)
    if cotacao and cotacao.emissao_id:
        messages.info(
            request,
            "Esta cotacao ja possui uma emissao vinculada. Abra a emissao para editar os dados finais.",
        )
        return redirect("admin_editar_emissao", cotacao.emissao_id)
    escalas_por_tipo = {"ida": [], "volta": []}
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, request.FILES, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        passageiros_json = _build_passageiros_json_for_context(request.POST)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.cliente and not emissao.cliente.ativo:
                return HttpResponse("Cliente inativo", status=403)
            tipo_emissao = form.cleaned_data.get("tipo_emissao") or "cliente"
            emissao_parceiro = tipo_emissao == "parceiro"
            conta = None
            if tipo_emissao == "administrada":
                conta = ContaFidelidade.objects.filter(
                    conta_administrada=emissao.conta_administrada,
                    programa=emissao.programa,
                ).select_related("programa").first()
            elif tipo_emissao == "cliente":
                conta = ContaFidelidade.objects.filter(
                    cliente=emissao.cliente, programa=emissao.programa
                ).select_related("programa").first()
            valor_medio_milheiro = None
            if tipo_emissao in ("cliente", "administrada") and conta:
                valor_medio_milheiro = conta.valor_medio_por_mil
                if (not valor_medio_milheiro or valor_medio_milheiro <= 0) and getattr(conta.programa, "preco_medio_milheiro", None):
                    valor_medio_milheiro = float(conta.programa.preco_medio_milheiro)
            elif tipo_emissao == "parceiro":
                valor_medio_milheiro = float(emissao.valor_milheiro_parceiro or 0)
            if tipo_emissao in ("cliente", "administrada") and not conta:
                form.add_error("programa", "Selecione um programa vinculado ao titular escolhido.")
                messages.error(
                    request,
                    "Não foi possível salvar a emissão: programa não vinculado ao titular selecionado.",
                )
            if form.errors:
                form.add_error(None, "Revise os campos destacados antes de salvar a emissão.")
            elif emissao.pontos_utilizados and (not valor_medio_milheiro or valor_medio_milheiro <= 0):
                form.add_error(
                    "programa",
                    "Valor médio do milheiro ausente para o titular selecionado. Atualize os dados antes de prosseguir.",
                )
                messages.error(
                    request,
                    "Não foi possível salvar a emissão: valor médio do milheiro ausente para o titular.",
                )
            else:
                passageiros = _parse_passageiros(request.POST)
                passageiros_errors = _validate_passageiros(passageiros)
                for err in passageiros_errors:
                    form.add_error(None, err)
                cpfs = [p.get("cpf") for p in passageiros if p.get("cpf")]
                try:
                    validar_limite_cpfs(conta, cpfs)
                except ValidationError as exc:
                    form.add_error(None, exc.message)
                if form.errors:
                    form.add_error(None, "Revise os campos destacados antes de salvar a emissão.")
                else:
                    with transaction.atomic():
                        criar_hotel_nome = (form.cleaned_data.get("criar_hotel_nome") or "").strip()
                        if criar_hotel_nome:
                            hotel = EmissaoHotel.objects.create(
                                cliente=emissao.cliente,
                                nome_hotel=criar_hotel_nome,
                                check_in=form.cleaned_data.get("criar_hotel_check_in") or emissao.data_ida.date(),
                                check_out=form.cleaned_data.get("criar_hotel_check_out") or emissao.data_ida.date(),
                                valor_referencia=Decimal("0"),
                                valor_pago=Decimal("0"),
                                economia_obtida=Decimal("0"),
                            )
                            emissao.hotel_vinculado = hotel
                        if tipo_emissao in ("cliente", "administrada") and valor_medio_milheiro is not None:
                            emissao.valor_milheiro_parceiro = Decimal(str(valor_medio_milheiro))
                        valor_milheiro = emissao.valor_milheiro_parceiro or 0
                        valor_referencia_pontos = calcular_custo_milhas(
                            emissao.pontos_utilizados or 0, valor_milheiro
                        )
                        emissao.valor_referencia_pontos = valor_referencia_pontos
                        incluir_taxas = tipo_emissao == "cliente"
                        custo_total = calcular_custo_total_emissao(
                            emissao, valor_milheiro, incluir_taxas=incluir_taxas
                        )
                        emissao.custo_total = custo_total
                        emissao.economia_obtida = calcular_economia(emissao, custo_total)
                        emissao.lucro = calcular_lucro_emissao(emissao, custo_total)
                        emissao.save()

                        total_passageiros_esperado = (emissao.qtd_adultos or 0) + (emissao.qtd_criancas or 0) + (emissao.qtd_bebes or 0)
                        total_passageiros_recebido = int(request.POST.get("total_passageiros", 0))

                        if total_passageiros_recebido != total_passageiros_esperado:
                            transaction.set_rollback(True)
                            form.add_error(
                                None,
                                f"Inconsistência no número de passageiros. Esperado: {total_passageiros_esperado}, Recebido: {total_passageiros_recebido}. Verifique se todos os passageiros foram preenchidos corretamente.",
                            )
                            messages.error(
                                request, "Não foi possível salvar a emissão. Inconsistência no número de passageiros."
                            )
                            return _render_nova_emissao_form(
                                request,
                                form=form,
                                empresa=empresa,
                                cliente_id=cliente_id,
                                passageiros_json=passageiros_json,
                                escalas_por_tipo=escalas_por_tipo,
                                cotacao_conversion=cotacao_conversion,
                            )

                        registrar_uso_cpfs(conta, cpfs, emissao.data_ida.date())
                        for passageiro in passageiros:
                            Passageiro.objects.create(
                                emissao=emissao,
                                nome=passageiro.get("nome"),
                                cpf=passageiro.get("cpf"),
                                rg=passageiro.get("rg"),
                                passaporte=passageiro.get("passaporte"),
                                passaporte_validade=passageiro.get("passaporte_validade"),
                                data_nascimento=passageiro.get("data_nascimento"),
                                observacoes=passageiro.get("observacoes"),
                                categoria=passageiro.get("categoria"),
                            )
                        for escala in escalas_payload:
                            Escala.objects.create(emissao=emissao, **escala)
                        if conta and not emissao_parceiro:
                            registrar_movimentacao_pontos(
                                conta,
                                emissao,
                                emissao.pontos_utilizados or 0,
                                emissao.valor_referencia_pontos or Decimal("0"),
                            )
                        if cotacao:
                            cotacao.status = "emissao"
                            cotacao.emissao = emissao
                            cotacao.save(update_fields=["status", "emissao"])
                        messages.success(request, "Emissão salva com sucesso.")
                        return redirect("admin_emissoes")
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
        else:
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
        return _render_nova_emissao_form(
            request,
            form=form,
            empresa=empresa,
            cliente_id=cliente_id,
            passageiros_json=passageiros_json,
            escalas_por_tipo=escalas_por_tipo,
            cotacao_conversion=cotacao_conversion,
        )
    else:
        if cotacao:
            initial = _build_emissao_initial_from_cotacao(cotacao)
            escalas_por_tipo = _format_escalas(
                cotacao.escalas.values("aeroporto_id", "duracao", "cidade", "tipo", "ordem")
            )
        else:
            initial = {"cliente": cliente_id} if cliente_id else {}
        form = EmissaoPassagemForm(initial=initial, empresa=empresa)
    return _render_nova_emissao_form(
        request,
        form=form,
        empresa=empresa,
        cliente_id=cliente_id,
        passageiros_json="[]",
        escalas_por_tipo=escalas_por_tipo,
        cotacao_conversion=cotacao_conversion,
    )


@login_required
def editar_emissao(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = get_object_or_404(
        scope_queryset_to_company(EmissaoPassagem.objects.all(), request, "cliente__empresa", "conta_administrada__empresa", "emissor_parceiro__empresa"),
        id=emissao_id,
    )
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    escalas_por_tipo = _format_escalas(
        emissao.escalas.values("aeroporto_id", "duracao", "cidade", "tipo", "ordem")
    )
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, request.FILES, instance=emissao, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            with transaction.atomic():
                emissao = form.save(commit=False)
                tipo_emissao = form.cleaned_data.get("tipo_emissao") or "cliente"
                emissao_parceiro = tipo_emissao == "parceiro"
                conta = None
                if tipo_emissao == "administrada":
                    conta = ContaFidelidade.objects.filter(
                        conta_administrada=emissao.conta_administrada,
                        programa=emissao.programa,
                    ).select_related("programa").first()
                elif tipo_emissao == "cliente":
                    conta = ContaFidelidade.objects.filter(
                        cliente=emissao.cliente, programa=emissao.programa
                    ).select_related("programa").first()
                valor_medio_milheiro = None
                if tipo_emissao in ("cliente", "administrada") and conta:
                    valor_medio_milheiro = conta.valor_medio_por_mil
                    if (not valor_medio_milheiro or valor_medio_milheiro <= 0) and getattr(conta.programa, "preco_medio_milheiro", None):
                        valor_medio_milheiro = float(conta.programa.preco_medio_milheiro)
                elif tipo_emissao == "parceiro":
                    valor_medio_milheiro = float(emissao.valor_milheiro_parceiro or 0)
                if tipo_emissao in ("cliente", "administrada") and not conta:
                    form.add_error("programa", "Selecione um programa vinculado ao titular escolhido.")
                    messages.error(
                        request,
                        "Não foi possível salvar a emissão: programa não vinculado ao titular selecionado.",
                    )
                if form.errors:
                    form.add_error(None, "Revise os campos destacados antes de salvar a emissão.")
                elif emissao.pontos_utilizados and (not valor_medio_milheiro or valor_medio_milheiro <= 0):
                    form.add_error(
                        "programa",
                        "Valor médio do milheiro ausente para o titular selecionado. Atualize os dados antes de prosseguir.",
                    )
                    messages.error(
                        request,
                        "Não foi possível salvar a emissão: valor médio do milheiro ausente para o titular.",
                    )
                else:
                    criar_hotel_nome = (form.cleaned_data.get("criar_hotel_nome") or "").strip()
                    if criar_hotel_nome:
                        hotel = EmissaoHotel.objects.create(
                            cliente=emissao.cliente,
                            nome_hotel=criar_hotel_nome,
                            check_in=form.cleaned_data.get("criar_hotel_check_in") or emissao.data_ida.date(),
                            check_out=form.cleaned_data.get("criar_hotel_check_out") or emissao.data_ida.date(),
                            valor_referencia=Decimal("0"),
                            valor_pago=Decimal("0"),
                            economia_obtida=Decimal("0"),
                        )
                        emissao.hotel_vinculado = hotel
                    passageiros = _parse_passageiros(request.POST)
                    passageiros_errors = _validate_passageiros(passageiros)
                    for err in passageiros_errors:
                        form.add_error(None, err)
                    cpfs = [p.get("cpf") for p in passageiros if p.get("cpf")]
                    try:
                        validar_limite_cpfs(conta, cpfs, emissao_id=emissao.id)
                    except ValidationError as exc:
                        form.add_error(None, exc.message)
                    if form.errors:
                        form.add_error(None, "Revise os campos destacados antes de salvar a emissão.")
                        transaction.set_rollback(True)
                        messages.error(
                            request,
                            "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
                        )
                        passageiros = _serialize_passageiros_list(list(
                            emissao.passageiros.filter(categoria="adulto").values(
                                "nome",
                                "cpf",
                                "rg",
                                "passaporte",
                                "passaporte_validade",
                                "data_nascimento",
                                "observacoes",
                                "categoria",
                            )
                        ))
                        passageiros += _serialize_passageiros_list(list(
                            emissao.passageiros.filter(categoria="crianca").values(
                                "nome",
                                "cpf",
                                "rg",
                                "passaporte",
                                "passaporte_validade",
                                "data_nascimento",
                                "observacoes",
                                "categoria",
                            )
                        ))
                        passageiros += _serialize_passageiros_list(list(
                            emissao.passageiros.filter(categoria="bebe").values(
                                "nome",
                                "cpf",
                                "rg",
                                "passaporte",
                                "passaporte_validade",
                                "data_nascimento",
                                "observacoes",
                                "categoria",
                            )
                        ))
                        return render(
                            request,
                            "admin_custom/form_emissao_passagem.html",
                            _build_emissao_template_context(
                                form=form,
                                empresa=empresa,
                                emissoes=EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida"),
                                passageiros_json=json.dumps(passageiros),
                                escalas_por_tipo=escalas_por_tipo,
                            ),
                        )

                    if tipo_emissao in ("cliente", "administrada") and valor_medio_milheiro is not None:
                        emissao.valor_milheiro_parceiro = Decimal(str(valor_medio_milheiro))
                    valor_milheiro = emissao.valor_milheiro_parceiro or 0
                    valor_referencia_pontos = calcular_custo_milhas(
                        emissao.pontos_utilizados or 0, valor_milheiro
                    )
                    emissao.valor_referencia_pontos = valor_referencia_pontos
                    incluir_taxas = tipo_emissao == "cliente"
                    custo_total = calcular_custo_total_emissao(
                        emissao, valor_milheiro, incluir_taxas=incluir_taxas
                    )
                    emissao.custo_total = custo_total
                    emissao.economia_obtida = calcular_economia(emissao, custo_total)
                    emissao.lucro = calcular_lucro_emissao(emissao, custo_total)
                    emissao.save()

                    total_passageiros_esperado = (emissao.qtd_adultos or 0) + (emissao.qtd_criancas or 0) + (emissao.qtd_bebes or 0)
                    total_passageiros_recebido = int(request.POST.get("total_passageiros", 0))

                    if total_passageiros_recebido != total_passageiros_esperado:
                        transaction.set_rollback(True)
                        form.add_error(
                            None,
                            f"Inconsistência no número de passageiros. Esperado: {total_passageiros_esperado}, Recebido: {total_passageiros_recebido}. Verifique se todos os passageiros foram preenchidos corretamente.",
                        )
                        messages.error(
                            request,
                            "Não foi possível salvar a emissão. Inconsistência no número de passageiros.",
                        )
                        passageiros = _serialize_passageiros_list(list(
                            emissao.passageiros.filter(categoria="adulto").values(
                                "nome",
                                "cpf",
                                "rg",
                                "passaporte",
                                "passaporte_validade",
                                "data_nascimento",
                                "observacoes",
                                "categoria",
                            )
                        ))
                        passageiros += _serialize_passageiros_list(list(
                            emissao.passageiros.filter(categoria="crianca").values(
                                "nome",
                                "cpf",
                                "rg",
                                "passaporte",
                                "passaporte_validade",
                                "data_nascimento",
                                "observacoes",
                                "categoria",
                            )
                        ))
                        passageiros += _serialize_passageiros_list(list(
                            emissao.passageiros.filter(categoria="bebe").values(
                                "nome",
                                "cpf",
                                "rg",
                                "passaporte",
                                "passaporte_validade",
                                "data_nascimento",
                                "observacoes",
                                "categoria",
                            )
                        ))
                        return render(
                            request,
                            "admin_custom/form_emissao_passagem.html",
                            _build_emissao_template_context(
                                form=form,
                                empresa=empresa,
                                emissoes=EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida"),
                                passageiros_json=json.dumps(passageiros),
                                escalas_por_tipo=escalas_por_tipo,
                            ),
                        )

                    registrar_uso_cpfs(conta, cpfs, emissao.data_ida.date())
                    emissao.passageiros.all().delete()
                    for passageiro in passageiros:
                        Passageiro.objects.create(
                            emissao=emissao,
                            nome=passageiro.get("nome"),
                            cpf=passageiro.get("cpf"),
                            rg=passageiro.get("rg"),
                            passaporte=passageiro.get("passaporte"),
                            passaporte_validade=passageiro.get("passaporte_validade"),
                            data_nascimento=passageiro.get("data_nascimento"),
                            observacoes=passageiro.get("observacoes"),
                            categoria=passageiro.get("categoria"),
                        )
                    emissao.escalas.all().delete()
                    for escala in escalas_payload:
                        Escala.objects.create(emissao=emissao, **escala)
                    if conta and not emissao_parceiro:
                        registrar_movimentacao_pontos(
                            conta, emissao, emissao.pontos_utilizados or 0, emissao.valor_referencia_pontos or Decimal("0")
                        )
                    messages.success(request, "Emissão atualizada com sucesso.")
                    return redirect("admin_emissoes")
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
        else:
            messages.error(
                request,
                "Não foi possível salvar a emissão. Corrija os campos destacados e tente novamente.",
            )
    else:
        form = EmissaoPassagemForm(instance=emissao, empresa=empresa)
    emissoes = scope_queryset_to_company(
        EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida"),
        request,
        "cliente__empresa",
        "conta_administrada__empresa",
        "emissor_parceiro__empresa",
    )
    passageiros = _serialize_passageiros_list(list(
        emissao.passageiros.filter(categoria="adulto").values(
            "nome",
            "cpf",
            "rg",
            "passaporte",
            "passaporte_validade",
            "data_nascimento",
            "observacoes",
            "categoria",
        )
    ))
    passageiros += _serialize_passageiros_list(list(
        emissao.passageiros.filter(categoria="crianca").values(
            "nome",
            "cpf",
            "rg",
            "passaporte",
            "passaporte_validade",
            "data_nascimento",
            "observacoes",
            "categoria",
        )
    ))
    passageiros += _serialize_passageiros_list(list(
        emissao.passageiros.filter(categoria="bebe").values(
            "nome",
            "cpf",
            "rg",
            "passaporte",
            "passaporte_validade",
            "data_nascimento",
            "observacoes",
            "categoria",
        )
    ))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        _build_emissao_template_context(
            form=form,
            empresa=empresa,
            emissoes=emissoes,
            passageiros_json=json.dumps(passageiros),
            escalas_por_tipo=escalas_por_tipo,
        ),
    )


@login_required
def emissao_pdf(request, emissao_id):
    """Download da emissão em formato PDF para o painel administrativo."""
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = _get_emissao_for_preview(request, emissao_id)
    return emissao_pdf_response(
        emissao,
        filename_prefix="emissao_preview",
        as_attachment=False,
    )


@login_required
def emissao_detalhe(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = _get_emissao_for_preview(request, emissao_id)
    ensure_acompanhamento_passagem(emissao)
    emissao = _get_emissao_for_preview(request, emissao_id)
    return render(
        request,
        "admin_custom/emissao_preview.html",
        {
            "emissao": emissao,
            "preview": build_emissao_preview_context(emissao),
            "menu_ativo": "emissoes",
        },
    )


@login_required
def emissao_acompanhamento(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = _get_emissao_for_preview(request, emissao_id)
    acompanhamento = ensure_acompanhamento_passagem(emissao)

    if request.method == "POST":
        form = AcompanhamentoPassagemForm(request.POST, instance=acompanhamento)
        if form.is_valid():
            acompanhamento = form.save()
            if "sincronizar" in request.POST:
                result = sync_acompanhamento_passagem(acompanhamento)
                if result.success:
                    messages.success(request, result.message)
                else:
                    messages.warning(request, result.message)
            else:
                messages.success(request, "Acompanhamento salvo com sucesso.")
            return redirect("admin_emissao_acompanhamento", emissao_id=emissao.id)
        messages.error(request, "Nao foi possivel salvar o acompanhamento. Revise os campos e tente novamente.")
    else:
        form = AcompanhamentoPassagemForm(instance=acompanhamento)

    return render(
        request,
        "admin_custom/emissao_acompanhamento.html",
        {
            "emissao": emissao,
            "acompanhamento": acompanhamento,
            "form": form,
            "menu_ativo": "emissoes",
        },
    )


@login_required
def deletar_emissao(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    emissao = get_object_or_404(
        scope_queryset_to_company(EmissaoPassagem.objects.all(), request, "cliente__empresa", "conta_administrada__empresa", "emissor_parceiro__empresa"),
        id=emissao_id,
    )
    emissao.delete()
    messages.success(request, "Emissão deletada com sucesso.")
    return redirect("admin_emissoes")


@login_required
def admin_hoteis(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    management_context = build_operational_dashboard_context(user=request.user, request=request)
    management_dashboard = management_context["management_dashboard"]
    active_filters = _current_management_filters(request)
    start_date = _management_filter_value(active_filters, "data_inicio")
    end_date = _management_filter_value(active_filters, "data_fim")
    selected_clientes = _management_filter_list(active_filters, "cliente")

    emissoes = scope_queryset_to_company(
        EmissaoHotel.objects.all().select_related("cliente__usuario"),
        request,
        "cliente__empresa",
    )
    if start_date:
        emissoes = emissoes.filter(check_in__gte=start_date)
    if end_date:
        emissoes = emissoes.filter(check_out__lte=end_date)
    if selected_clientes:
        emissoes = emissoes.filter(cliente_id__in=selected_clientes)

    total = emissoes.count()
    valor_referencia_total = sum((e.valor_referencia or 0) for e in emissoes)
    valor_pago_total = sum((e.valor_pago or 0) for e in emissoes)
    economia_total = sum((e.economia_obtida or 0) for e in emissoes)
    return render(
        request,
        "admin_custom/hoteis.html",
        {
            "emissoes": emissoes.order_by("-check_in"),
            "hotel_totais": {
                "total": total,
                "referencia": f"R$ {valor_referencia_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "pago": f"R$ {valor_pago_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                "economia": f"R$ {economia_total:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            },
            "management_dashboard": management_dashboard,
            "menu_ativo": "hoteis",
        },
    )


@login_required
def nova_emissao_hotel(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    if request.method == "POST":
        form = EmissaoHotelForm(request.POST)
        if form.is_valid():
            emissao = form.save(commit=False)
            if not emissao.cliente.ativo:
                return HttpResponse("Cliente inativo", status=403)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
            emissao.save()
            return redirect("admin_hoteis")
    else:
        form = EmissaoHotelForm()
    return render(
        request,
        "admin_custom/form_hotel.html",
        {"form": form, "menu_ativo": "hoteis"},
    )


@login_required
def editar_emissao_hotel(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = get_object_or_404(
        scope_queryset_to_company(EmissaoHotel.objects.all(), request, "cliente__empresa"),
        id=emissao_id,
    )
    if request.method == "POST":
        form = EmissaoHotelForm(request.POST, instance=emissao)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.valor_referencia and emissao.valor_pago:
                emissao.economia_obtida = emissao.valor_referencia - emissao.valor_pago
            emissao.save()
            return redirect("admin_hoteis")
    else:
        form = EmissaoHotelForm(instance=emissao)
    return render(
        request,
        "admin_custom/form_hotel.html",
        {"form": form, "menu_ativo": "hoteis"},
    )


@login_required
def deletar_emissao_hotel(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    emissao = get_object_or_404(
        scope_queryset_to_company(EmissaoHotel.objects.all(), request, "cliente__empresa"),
        id=emissao_id,
    )
    emissao.delete()
    messages.success(request, "Emissão deletada com sucesso.")
    return redirect("admin_hoteis")
