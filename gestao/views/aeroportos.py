from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import AeroportoForm
from ..models import Aeroporto
from .permissions import require_admin_or_operator


@login_required
def admin_aeroportos(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    busca = request.GET.get("busca", "")
    aeroportos = Aeroporto.objects.all()
    if busca:
        aeroportos = aeroportos.filter(Q(nome__icontains=busca) | Q(sigla__icontains=busca))
    return render(
        request,
        "admin_custom/aeroportos.html",
        {"aeroportos": aeroportos, "busca": busca},
    )


@login_required
def criar_aeroporto(request):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    if request.method == "POST":
        form = AeroportoForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("admin_aeroportos")
    else:
        form = AeroportoForm()
    return render(request, "admin_custom/form_aeroporto.html", {"form": form})


@login_required
def deletar_aeroporto(request, aeroporto_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    perfil = getattr(getattr(request.user, "cliente_gestao", None), "perfil", "")
    if perfil != "admin":
        return render(request, "sem_permissao.html")
    Aeroporto.objects.filter(id=aeroporto_id).delete()
    messages.success(request, "Aeroporto deletado com sucesso.")
    return redirect("admin_aeroportos")


@login_required
def editar_aeroporto(request, aeroporto_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    aeroporto = get_object_or_404(Aeroporto, id=aeroporto_id)
    if request.method == "POST":
        form = AeroportoForm(request.POST, instance=aeroporto)
        if form.is_valid():
            form.save()
            return redirect("admin_aeroportos")
    else:
        form = AeroportoForm(instance=aeroporto)
    return render(request, "admin_custom/form_aeroporto.html", {"form": form})
