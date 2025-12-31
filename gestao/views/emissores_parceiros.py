from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .permissions import require_admin_or_operator
from ..forms import EmissorParceiroForm
from ..models import EmissorParceiro


@login_required
def admin_emissores_parceiros(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissores = EmissorParceiro.objects.all().prefetch_related("programas")
    if empresa:
        emissores = emissores.filter(empresa=empresa)
    return render(
        request,
        "admin_custom/emissores_parceiros.html",
        {"emissores": emissores},
    )


@login_required
def criar_emissor_parceiro(request):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    if request.method == "POST":
        form = EmissorParceiroForm(request.POST)
        if form.is_valid():
            emissor = form.save(commit=False)
            emissor.empresa = empresa
            emissor.save()
            form.save_m2m()
            return redirect("admin_emissores_parceiros")
    else:
        form = EmissorParceiroForm()
    return render(request, "admin_custom/form_emissor_parceiro.html", {"form": form})


@login_required
def editar_emissor_parceiro(request, emissor_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissor = get_object_or_404(EmissorParceiro, id=emissor_id)
    if empresa and emissor.empresa != empresa:
        return render(request, "sem_permissao.html")
    if request.method == "POST":
        form = EmissorParceiroForm(request.POST, instance=emissor)
        if form.is_valid():
            form.save()
            return redirect("admin_emissores_parceiros")
    else:
        form = EmissorParceiroForm(instance=emissor)
    return render(
        request, "admin_custom/form_emissor_parceiro.html", {"form": form}
    )


@login_required
def deletar_emissor_parceiro(request, emissor_id):
    if permission_denied := require_admin_or_operator(request):
        return permission_denied
    empresa = getattr(getattr(request.user, "cliente_gestao", None), "empresa", None)
    emissor = get_object_or_404(EmissorParceiro, id=emissor_id)
    if empresa and emissor.empresa != empresa:
        return render(request, "sem_permissao.html")
    emissor.delete()
    return redirect("admin_emissores_parceiros")
