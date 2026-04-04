from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404

from accounts.access import user_has_admin_panel_access

from ..forms import EmpresaDocumentTextsForm, EmpresaForm, EmpresaManagementForm, EmpresaProfileForm
from ..models import Cliente, Empresa


def require_superadmin(request):
    if not request.user.is_superuser or not user_has_admin_panel_access(request.user):
        return render(request, "sem_permissao.html")
    return None


def require_company_admin(request):
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin" and not request.user.is_superuser:
        return render(request, "sem_permissao.html")
    return None


@login_required
def empresas_list(request):
    if (permission_denied := require_superadmin(request)):
        return permission_denied
    empresas = Empresa.objects.all().select_related("admin__usuario")
    empresas_info = []
    total_operadores = 0
    total_clientes = 0
    empresas_ativas = 0
    empresas_bloqueadas = 0
    for empresa in empresas:
        operadores = empresa.total_operadores_ativos()
        clientes = empresa.total_clientes_ativos()
        total_operadores += operadores
        total_clientes += clientes
        if empresa.ativo:
            empresas_ativas += 1
        if empresa.limite_colaboradores == 0:
            empresas_bloqueadas += 1
        empresas_info.append(
            {
                "empresa": empresa,
                "operadores": operadores,
                "clientes": clientes,
                "vagas": empresa.vagas_colaboradores(),
                "limite_atingido": empresa.limite_colaboradores_atingido(),
            }
        )
    return render(
        request,
        "admin_custom/empresas.html",
        {
            "empresas_info": empresas_info,
            "totais": {
                "empresas": len(empresas_info),
                "ativas": empresas_ativas,
                "operadores": total_operadores,
                "clientes": total_clientes,
                "bloqueadas": empresas_bloqueadas,
            },
            "menu_ativo": "empresas",
        },
    )


@login_required
def criar_empresa(request):
    if (permission_denied := require_superadmin(request)):
        return permission_denied
    if request.method == "POST":
        form = EmpresaForm(request.POST, request.FILES)
        if form.is_valid():
            empresa = form.save(criado_por=request.user)
            messages.success(request, f"Empresa {empresa.nome} criada com sucesso.")
            return redirect("admin_empresas")
    else:
        form = EmpresaForm()
    return render(
        request,
        "admin_custom/empresa_form.html",
        {
            "form": form,
            "menu_ativo": "empresas",
            "is_editing": False,
            "page_title": "Nova Empresa",
            "page_subtitle": "Cadastre uma nova empresa e ja vincule o administrador inicial.",
            "hero_title": "Criar nova empresa",
            "hero_subtitle": "Defina dados da organizacao, capacidade operacional e o administrador inicial em uma unica tela.",
            "submit_label": "Salvar empresa",
        },
    )


@login_required
def editar_empresa(request, empresa_id):
    if (permission_denied := require_superadmin(request)):
        return permission_denied

    empresa = get_object_or_404(Empresa.objects.select_related("admin__usuario"), pk=empresa_id)
    if request.method == "POST":
        form = EmpresaManagementForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            empresa = form.save()
            messages.success(request, f"Empresa {empresa.nome} atualizada com sucesso.")
            return redirect("admin_empresas")
    else:
        form = EmpresaManagementForm(instance=empresa)

    admin_cliente = getattr(empresa, "admin", None)
    admin_user = getattr(admin_cliente, "usuario", None)
    return render(
        request,
        "admin_custom/empresa_form.html",
        {
            "form": form,
            "menu_ativo": "empresas",
            "empresa": empresa,
            "admin_cliente": admin_cliente,
            "admin_user": admin_user,
            "is_editing": True,
            "page_title": f"Editar Empresa | {empresa.nome}",
            "page_subtitle": "Atualize dados da organizacao, capacidade operacional e status comercial.",
            "hero_title": f"Editar {empresa.nome}",
            "hero_subtitle": "O superadmin controla dados institucionais, limite de colaboradores e ativacao da empresa.",
            "submit_label": "Salvar alteracoes",
            "operadores_ativos": empresa.total_operadores_ativos(),
            "clientes_ativos": empresa.total_clientes_ativos(),
            "vagas_disponiveis": empresa.vagas_colaboradores(),
        },
    )


@login_required
def configurar_empresa(request):
    if (permission_denied := require_company_admin(request)):
        return permission_denied

    cliente_admin = getattr(request.user, "cliente_gestao", None)
    empresa = getattr(cliente_admin, "empresa", None)
    if not empresa:
        messages.error(request, "Nao foi possivel localizar a empresa vinculada ao seu acesso.")
        return redirect("admin_dashboard")

    if request.method == "POST":
        form = EmpresaProfileForm(request.POST, request.FILES, instance=empresa)
        if form.is_valid():
            empresa = form.save(commit=False)
            if not empresa.responsavel_nome and cliente_admin and getattr(cliente_admin, "usuario", None):
                empresa.responsavel_nome = cliente_admin.usuario.get_full_name() or cliente_admin.usuario.username
            if not empresa.email_contato and cliente_admin and getattr(cliente_admin, "usuario", None):
                empresa.email_contato = cliente_admin.usuario.email or ""
            empresa.save()
            messages.success(request, "Dados da empresa atualizados com sucesso.")
            return redirect("admin_empresa_configuracoes")
    else:
        initial = {}
        if not empresa.responsavel_nome and cliente_admin and getattr(cliente_admin, "usuario", None):
            initial["responsavel_nome"] = cliente_admin.usuario.get_full_name() or cliente_admin.usuario.username
        if not empresa.email_contato and cliente_admin and getattr(cliente_admin, "usuario", None):
            initial["email_contato"] = cliente_admin.usuario.email or ""
        form = EmpresaProfileForm(instance=empresa, initial=initial)

    admin_user = getattr(getattr(empresa, "admin", None), "usuario", None)
    return render(
        request,
        "admin_custom/empresa_configuracoes.html",
        {
            "form": form,
            "empresa": empresa,
            "admin_user": admin_user,
            "menu_ativo": "empresa_config",
        },
    )


@login_required
def configurar_empresa_textos(request):
    if (permission_denied := require_company_admin(request)):
        return permission_denied

    cliente_admin = getattr(request.user, "cliente_gestao", None)
    empresa = getattr(cliente_admin, "empresa", None)
    if not empresa:
        messages.error(request, "Nao foi possivel localizar a empresa vinculada ao seu acesso.")
        return redirect("admin_dashboard")

    if request.method == "POST":
        form = EmpresaDocumentTextsForm(request.POST, instance=empresa)
        if form.is_valid():
            form.save()
            messages.success(request, "Textos de cotacao e emissao atualizados com sucesso.")
            return redirect("admin_empresa_textos")
    else:
        form = EmpresaDocumentTextsForm(instance=empresa)

    return render(
        request,
        "admin_custom/empresa_textos_documentos.html",
        {
            "form": form,
            "empresa": empresa,
            "menu_ativo": "empresa_textos",
        },
    )
