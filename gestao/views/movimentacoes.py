from django import forms
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import ContaFidelidade, Movimentacao
from .permissions import require_admin_or_operator


class NovaMovimentacaoForm(forms.ModelForm):
    class Meta:
        model = Movimentacao
        fields = ["data", "pontos", "valor_pago", "descricao"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "descricao": forms.TextInput(attrs={"placeholder": "Descrição"}),
        }


@login_required
def admin_movimentacoes(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    movimentacoes = conta.movimentacoes.all()
    return render(
        request,
        "admin_custom/movimentacoes.html",
        {
            "conta": conta,
            "movimentacoes": movimentacoes,
        },
    )


@login_required
def admin_nova_movimentacao(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(ContaFidelidade, id=conta_id)
    if not conta.cliente.ativo:
        return HttpResponse("Cliente inativo", status=403)
    if request.method == "POST":
        form = NovaMovimentacaoForm(request.POST)
        if form.is_valid():
            mov = form.save(commit=False)
            mov.conta = conta
            mov.save()
            return redirect("admin_movimentacoes", conta_id=conta.id)
    else:
        form = NovaMovimentacaoForm()
    return render(
        request,
        "admin_custom/nova_movimentacao.html",
        {
            "form": form,
            "conta": conta,
        },
    )
