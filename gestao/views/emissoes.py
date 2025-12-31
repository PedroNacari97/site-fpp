from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import HttpResponse
from django.contrib import messages
from decimal import Decimal
from gestao.models import ContaFidelidade, Movimentacao, AcessoClienteLog
from painel_cliente.views import build_dashboard_context
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
    Escala,
    CompanhiaAerea,
    EmissorParceiro,
)
from services.pdf_service import emissao_pdf_response
import csv
import json
from datetime import timedelta

from .permissions import require_admin_or_operator
from gestao.services.emissao_financeiro import (
    calcular_economia,
    calcular_valor_referencia_pontos,
    registrar_movimentacao_pontos,
)
from gestao.services.clientes_programas import (
    build_clientes_programas_map,
    build_contas_administradas_programas_map,
)
from gestao.services.cpf_limite import validar_limite_cpfs
from gestao.utils import normalize_cpf, parse_br_date, validate_cpf_digits


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
            if row.get(field):
                row[field] = row[field].isoformat()
    return passageiros


def _build_emissor_parceiros_map(empresa=None):
    emissores = EmissorParceiro.objects.filter(ativo=True).prefetch_related("programas")
    if empresa:
        emissores = emissores.filter(empresa=empresa)
    return {str(e.id): list(e.programas.values_list("id", flat=True)) for e in emissores}


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
        passageiro["cpf"] = normalized_cpf
        passageiro["nome"] = nome
        passageiro["passaporte"] = passaporte
        passageiro["rg"] = (passageiro.get("rg") or "").strip()
        passageiro["observacoes"] = (passageiro.get("observacoes") or "").strip()
    return errors


# --- EMISSÕES ---
@login_required
def admin_emissoes(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    programa_id = request.GET.get("programa")
    cliente_id = request.GET.get("cliente")
    q = request.GET.get("q")
    data_ini = request.GET.get("data_ini")
    data_fim = request.GET.get("data_fim")

    emissoes = EmissaoPassagem.objects.filter(
        Q(cliente__perfil="cliente", cliente__ativo=True) | Q(conta_administrada__isnull=False)
    ).select_related(
        "cliente",
        "programa",
        "aeroporto_partida",
        "aeroporto_destino",
        "conta_administrada",
    )
    if programa_id:
        emissoes = emissoes.filter(programa_id=programa_id)
    if cliente_id:
        emissoes = emissoes.filter(cliente_id=cliente_id)
    if q:
        emissoes = emissoes.filter(
            Q(aeroporto_partida__sigla__icontains=q)
            | Q(aeroporto_destino__sigla__icontains=q)
            | Q(aeroporto_partida__nome__icontains=q)
            | Q(aeroporto_destino__nome__icontains=q)
            | Q(cliente__usuario__username__icontains=q)
        )
    if data_ini:
        emissoes = emissoes.filter(data_ida__gte=data_ini)
    if data_fim:
        emissoes = emissoes.filter(data_volta__lte=data_fim)

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
                "Valor Pago",
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
                    e.valor_pago,
                    e.pontos_utilizados,
                    e.economia_obtida,
                    e.detalhes,
                ]
            )
        return response

    programas = ProgramaFidelidade.objects.all()
    clientes = Cliente.objects.filter(perfil="cliente", ativo=True).select_related("usuario")
    return render(
        request,
        "admin_custom/emissoes.html",
        {
            "emissoes": emissoes,
            "programas": programas,
            "clientes": clientes,
            "params": request.GET,
        },
    )


@login_required
def nova_emissao(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    cliente_id = request.GET.get("cliente_id")
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    escalas_por_tipo = {"ida": [], "volta": []}
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            emissao = form.save(commit=False)
            if emissao.cliente and not emissao.cliente.ativo:
                return HttpResponse("Cliente inativo", status=403)
            if emissao.conta_administrada_id:
                conta = ContaFidelidade.objects.filter(
                    conta_administrada=emissao.conta_administrada,
                    programa=emissao.programa,
                ).select_related("programa").first()
            else:
                conta = ContaFidelidade.objects.filter(
                    cliente=emissao.cliente, programa=emissao.programa
                ).select_related("programa").first()
            valor_medio_milheiro = None
            if conta:
                valor_medio_milheiro = conta.valor_medio_por_mil
                if (not valor_medio_milheiro or valor_medio_milheiro <= 0) and getattr(conta.programa, "preco_medio_milheiro", None):
                    valor_medio_milheiro = float(conta.programa.preco_medio_milheiro)
            if not conta:
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
                        valor_referencia_pontos = calcular_valor_referencia_pontos(
                            emissao.pontos_utilizados or 0, valor_medio_milheiro
                        )
                        emissao.valor_referencia_pontos = valor_referencia_pontos
                        emissao.economia_obtida = calcular_economia(emissao, valor_referencia_pontos)
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
                            emissoes = EmissaoPassagem.objects.all().order_by("-data_ida")
                            aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
                            return render(
                                request,
                                "admin_custom/form_emissao_passagem.html",
                                {
                                    "form": form,
                                    "emissoes": emissoes,
                                    "passageiros_json": "[]",
                                    "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
                                    "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
                                    "aeroportos_json": json.dumps(aeroportos),
                                    "cliente_id": cliente_id,
                                    "cliente_programas_json": json.dumps(
                                        build_clientes_programas_map(empresa_id=getattr(empresa, "id", None))
                                    ),
                                    "contas_adm_programas_json": json.dumps(
                                        build_contas_administradas_programas_map(
                                            empresa_id=getattr(empresa, "id", None)
                                        )
                                    ),
                                    "emissor_parceiros_json": json.dumps(
                                        _build_emissor_parceiros_map(empresa)
                                    ),
                                },
                            )

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
                        registrar_movimentacao_pontos(
                            conta,
                            emissao,
                            emissao.pontos_utilizados or 0,
                            emissao.valor_referencia_pontos or Decimal("0"),
                        )
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
    else:
        initial = {"cliente": cliente_id} if cliente_id else {}
        form = EmissaoPassagemForm(initial=initial, empresa=empresa)
    emissoes = EmissaoPassagem.objects.all().order_by("-data_ida")
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        {
            "form": form,
            "emissoes": emissoes,
            "passageiros_json": "[]",
            "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
            "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_id": cliente_id,
            "cliente_programas_json": json.dumps(build_clientes_programas_map(empresa_id=getattr(empresa, "id", None))),
            "contas_adm_programas_json": json.dumps(
                build_contas_administradas_programas_map(
                    empresa_id=getattr(empresa, "id", None)
                )
            ),
            "emissor_parceiros_json": json.dumps(_build_emissor_parceiros_map(empresa)),
        },
    )


@login_required
def editar_emissao(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = EmissaoPassagem.objects.get(id=emissao_id)
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    escalas_por_tipo = _format_escalas(
        emissao.escalas.values("aeroporto_id", "duracao", "cidade", "tipo", "ordem")
    )
    if request.method == "POST":
        form = EmissaoPassagemForm(request.POST, instance=emissao, empresa=empresa)
        escalas_payload = _build_escalas_from_request(request)
        escalas_por_tipo = _format_escalas(escalas_payload)
        if form.is_valid():
            with transaction.atomic():
                emissao = form.save(commit=False)
                if emissao.conta_administrada_id:
                    conta = ContaFidelidade.objects.filter(
                        conta_administrada=emissao.conta_administrada,
                        programa=emissao.programa,
                    ).select_related("programa").first()
                else:
                    conta = ContaFidelidade.objects.filter(
                        cliente=emissao.cliente, programa=emissao.programa
                    ).select_related("programa").first()
                valor_medio_milheiro = None
                if conta:
                    valor_medio_milheiro = conta.valor_medio_por_mil
                    if (not valor_medio_milheiro or valor_medio_milheiro <= 0) and getattr(conta.programa, "preco_medio_milheiro", None):
                        valor_medio_milheiro = float(conta.programa.preco_medio_milheiro)
                if not conta:
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
                        aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
                        return render(
                            request,
                            "admin_custom/form_emissao_passagem.html",
                            {
                                "form": form,
                                "emissoes": EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida"),
                                "passageiros_json": json.dumps(passageiros),
                                "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
                                "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
                                "aeroportos_json": json.dumps(aeroportos),
                                "cliente_programas_json": json.dumps(
                                    build_clientes_programas_map(emissao, empresa_id=getattr(empresa, "id", None))
                                ),
                                "contas_adm_programas_json": json.dumps(
                                    build_contas_administradas_programas_map(
                                        empresa_id=getattr(empresa, "id", None), instance=emissao
                                    )
                                ),
                                "emissor_parceiros_json": json.dumps(
                                    _build_emissor_parceiros_map(empresa)
                                ),
                            },
                        )

                    valor_referencia_pontos = calcular_valor_referencia_pontos(
                        emissao.pontos_utilizados or 0, valor_medio_milheiro
                    )
                    emissao.valor_referencia_pontos = valor_referencia_pontos
                    emissao.economia_obtida = calcular_economia(emissao, valor_referencia_pontos)
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
                        aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
                        return render(
                            request,
                            "admin_custom/form_emissao_passagem.html",
                            {
                                "form": form,
                                "emissoes": EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida"),
                                "passageiros_json": json.dumps(passageiros),
                                "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
                                "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
                                "aeroportos_json": json.dumps(aeroportos),
                                "cliente_programas_json": json.dumps(
                                    build_clientes_programas_map(emissao, empresa_id=getattr(empresa, "id", None))
                                ),
                                "contas_adm_programas_json": json.dumps(
                                    build_contas_administradas_programas_map(
                                        empresa_id=getattr(empresa, "id", None), instance=emissao
                                    )
                                ),
                                "emissor_parceiros_json": json.dumps(
                                    _build_emissor_parceiros_map(empresa)
                                ),
                            },
                        )

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
    emissoes = EmissaoPassagem.objects.exclude(id=emissao_id).order_by("-data_ida")
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
    aeroportos = list(Aeroporto.objects.values("id", "nome", "sigla"))
    return render(
        request,
        "admin_custom/form_emissao_passagem.html",
        {
            "form": form,
            "emissoes": emissoes,
            "passageiros_json": json.dumps(passageiros),
            "escalas_ida_json": json.dumps(escalas_por_tipo["ida"]),
            "escalas_volta_json": json.dumps(escalas_por_tipo["volta"]),
            "aeroportos_json": json.dumps(aeroportos),
            "cliente_programas_json": json.dumps(
                build_clientes_programas_map(emissao, empresa_id=getattr(empresa, "id", None))
            ),
            "contas_adm_programas_json": json.dumps(
                build_contas_administradas_programas_map(
                    empresa_id=getattr(empresa, "id", None), instance=emissao
                )
            ),
            "emissor_parceiros_json": json.dumps(_build_emissor_parceiros_map(empresa)),
        },
    )


@login_required
def emissao_pdf(request, emissao_id):
    """Download da emissão em formato PDF para o painel administrativo."""
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = get_object_or_404(EmissaoPassagem, id=emissao_id)
    return emissao_pdf_response(emissao)


@login_required
def emissao_detalhe(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = get_object_or_404(EmissaoPassagem, id=emissao_id)
    passageiros = list(
        emissao.passageiros.all().order_by("categoria", "nome")
    )
    cpfs_consumidos = len({normalize_cpf(p.cpf) for p in passageiros if p.cpf})
    return render(
        request,
        "admin_custom/emissao_detalhe.html",
        {
            "emissao": emissao,
            "passageiros": passageiros,
            "cpfs_consumidos": cpfs_consumidos,
        },
    )


@login_required
def deletar_emissao(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    EmissaoPassagem.objects.filter(id=emissao_id).delete()
    messages.success(request, "Emissão deletada com sucesso.")
    return redirect("admin_emissoes")


@login_required
def admin_hoteis(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    busca = request.GET.get("busca", "")
    emissoes = EmissaoHotel.objects.all().select_related("cliente__usuario")
    if busca:
        emissoes = emissoes.filter(
            Q(cliente__usuario__username__icontains=busca)
            | Q(cliente__usuario__first_name__icontains=busca)
            | Q(nome_hotel__icontains=busca)
        )
    return render(
        request, "admin_custom/hoteis.html", {"emissoes": emissoes, "busca": busca}
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
    return render(request, "admin_custom/form_hotel.html", {"form": form})


@login_required
def editar_emissao_hotel(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    emissao = EmissaoHotel.objects.get(id=emissao_id)
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
    return render(request, "admin_custom/form_hotel.html", {"form": form})


@login_required
def deletar_emissao_hotel(request, emissao_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    EmissaoHotel.objects.filter(id=emissao_id).delete()
    messages.success(request, "Emissão deletada com sucesso.")
    return redirect("admin_hoteis")
