from decimal import Decimal, ROUND_HALF_UP

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from gestao.utils import parse_br_date

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


class TransferenciaPontosForm(forms.Form):
    conta_origem = forms.ModelChoiceField(queryset=ContaFidelidade.objects.none())
    conta_destino = forms.ModelChoiceField(queryset=ContaFidelidade.objects.none())
    data = forms.DateField(
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "DD/MM/AAAA",
                "data-mask": "date",
                "inputmode": "numeric",
                "maxlength": "10",
            }
        ),
    )
    pontos = forms.IntegerField(min_value=1)
    bonus_percentual = forms.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, required=False, initial=0
    )

    def __init__(self, cliente, conta_inicial=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        contas_qs = ContaFidelidade.objects.filter(
            cliente=cliente, cliente__perfil="cliente", cliente__ativo=True
        ).select_related("programa")
        self.fields["conta_origem"].queryset = contas_qs
        self.fields["conta_destino"].queryset = contas_qs
        if conta_inicial:
            self.fields["conta_origem"].initial = conta_inicial

    def clean_data(self):
        return parse_br_date(self.cleaned_data.get("data"), field_label="Data da transferência") or timezone.now().date()

    def clean(self):
        cleaned = super().clean()
        origem = cleaned.get("conta_origem")
        destino = cleaned.get("conta_destino")
        pontos = cleaned.get("pontos") or 0
        if not origem or not destino:
            return cleaned
        if origem == destino:
            raise forms.ValidationError("A conta de origem e de destino devem ser diferentes.")
        if origem.cliente != destino.cliente:
            raise forms.ValidationError("A transferência deve ocorrer entre contas do mesmo cliente.")
        if origem.saldo_pontos < pontos:
            raise forms.ValidationError("Saldo insuficiente na conta de origem para concluir a transferência.")
        return cleaned


@login_required
def admin_movimentacoes(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(
        ContaFidelidade, id=conta_id, cliente__perfil="cliente"
    )
    movimentacoes = conta.movimentacoes_compartilhadas.order_by("-data")
    conta_base = conta.conta_saldo()
    return render(
        request,
        "admin_custom/movimentacoes.html",
        {
            "conta": conta,
            "conta_base": conta_base,
            "movimentacoes": movimentacoes,
        },
    )


@login_required
def admin_nova_movimentacao(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(
        ContaFidelidade, id=conta_id, cliente__perfil="cliente"
    )
    if conta.programa.is_vinculado:
        base_conta = conta.conta_saldo()
        messages.error(
            request,
            "O saldo é controlado pelo programa base. Crie movimentações direto no programa principal.",
        )
        return redirect("admin_movimentacoes", conta_id=base_conta.id)
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


@login_required
def admin_transferir_pontos(request, conta_id):
    if (permission_denied := require_admin_or_operator(request)):
        return permission_denied
    conta = get_object_or_404(ContaFidelidade, id=conta_id, cliente__perfil="cliente")
    if conta.programa.is_vinculado:
        base_conta = conta.conta_saldo()
        messages.error(
            request,
            "Transferências devem ser feitas pelo programa principal vinculado.",
        )
        return redirect("admin_transferir_pontos", conta_id=base_conta.id)
    if not conta.cliente.ativo:
        return HttpResponse("Cliente inativo", status=403)

    if request.method == "POST":
        form = TransferenciaPontosForm(conta.cliente, conta_inicial=conta, data=request.POST)
        if form.is_valid():
            origem = form.cleaned_data["conta_origem"]
            destino = form.cleaned_data["conta_destino"]
            data_transferencia = form.cleaned_data.get("data") or timezone.now().date()
            pontos = form.cleaned_data["pontos"]
            bonus_percentual = Decimal(form.cleaned_data.get("bonus_percentual") or 0)
            fator_bonus = Decimal("1") + (bonus_percentual / Decimal("100"))
            total_pontos_destino = int(
                (Decimal(pontos) * fator_bonus).to_integral_value(rounding=ROUND_HALF_UP)
            )
            custo_transferencia = (
                Decimal(origem.valor_medio_por_mil) * Decimal(pontos) / Decimal("1000")
            ).quantize(Decimal("0.01"))

            with transaction.atomic():
                Movimentacao.objects.create(
                    conta=origem,
                    data=data_transferencia,
                    pontos=-pontos,
                    valor_pago=-custo_transferencia,
                    descricao=f"Transferência para {destino.programa.nome}",
                )
                Movimentacao.objects.create(
                    conta=destino,
                    data=data_transferencia,
                    pontos=total_pontos_destino,
                    valor_pago=custo_transferencia,
                    descricao=(
                        f"Transferência de {origem.programa.nome} (+{bonus_percentual}% bônus)"
                        if bonus_percentual
                        else f"Transferência de {origem.programa.nome}"
                    ),
                )
            messages.success(
                request,
                "Transferência realizada com sucesso. Saldos e custo médio atualizados.",
            )
            return redirect("admin_movimentacoes", conta_id=conta.id)
    else:
        form = TransferenciaPontosForm(conta.cliente, conta_inicial=conta)

    return render(
        request,
        "admin_custom/transferencia_pontos.html",
        {
            "form": form,
            "conta": conta,
        },
    )
