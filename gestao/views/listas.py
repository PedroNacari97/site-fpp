from django.contrib.auth.decorators import login_required
from django.db.models import Prefetch, Q
from django.http import JsonResponse

from ..models import Cliente, ContaAdministrada, ContaFidelidade, ProgramaFidelidade
from .permissions import require_admin_or_operator


def _get_user_empresa(request):
    return getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)


@login_required
def api_clientes(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    empresa = _get_user_empresa(request)
    clientes = Cliente.objects.filter(perfil="cliente").select_related("usuario", "empresa")
    if empresa:
        clientes = clientes.filter(empresa=empresa)

    contas_qs = ContaFidelidade.objects.filter(
        conta_administrada__isnull=True
    ).select_related("programa", "programa__programa_base")
    if empresa:
        contas_qs = contas_qs.filter(cliente__empresa=empresa)

    clientes = clientes.prefetch_related(
        Prefetch("contafidelidade_set", queryset=contas_qs, to_attr="contas_fidelidade_list")
    ).order_by("usuario__first_name", "usuario__last_name", "usuario__username")

    resultados = []
    for cliente in clientes:
        pontos_por_conta = {}
        for conta in getattr(cliente, "contas_fidelidade_list", []):
            conta_base = conta.conta_saldo()
            pontos_por_conta[conta_base.id] = conta_base.saldo_pontos
        carteira = sum(pontos_por_conta.values())
        resultados.append(
            {
                "id": cliente.id,
                "nome": str(cliente),
                "segmento": "Corporativo" if cliente.empresa_id else "Individual",
                "status": "Ativo" if cliente.ativo else "Inativo",
                "carteira": carteira,
            }
        )

    return JsonResponse({"resultados": resultados})


@login_required
def api_contas(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    empresa = _get_user_empresa(request)
    contas = ContaAdministrada.objects.select_related(
        "empresa", "empresa__admin", "empresa__admin__usuario"
    )
    if empresa:
        contas = contas.filter(empresa=empresa)

    resultados = []
    for conta in contas.order_by("nome"):
        responsavel = ""
        if conta.empresa and conta.empresa.admin:
            responsavel = (
                conta.empresa.admin.usuario.get_full_name()
                or conta.empresa.admin.usuario.username
            )
        resultados.append(
            {
                "id": conta.id,
                "conta": conta.nome,
                "responsavel": responsavel,
                "limite": conta.empresa.limite_colaboradores if conta.empresa else 0,
                "status": "Ativa" if conta.ativo else "Inativa",
            }
        )

    return JsonResponse({"resultados": resultados})


@login_required
def api_programas(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied

    empresa = _get_user_empresa(request)
    programas = ProgramaFidelidade.objects.select_related("programa_base")
    if empresa:
        programas = programas.filter(
            Q(contafidelidade__cliente__empresa=empresa)
            | Q(contafidelidade__conta_administrada__empresa=empresa)
        ).distinct()

    resultados = []
    for programa in programas.order_by("nome"):
        parceiros = programa.descricao.strip() if programa.descricao else ""
        if not parceiros and programa.programa_base:
            parceiros = programa.programa_base.nome
        resultados.append(
            {
                "id": programa.id,
                "nome": programa.nome,
                "parceiros": parceiros,
                "status": programa.get_tipo_display(),
            }
        )

    return JsonResponse({"resultados": resultados})
