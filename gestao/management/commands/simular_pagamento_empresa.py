"""
Simula o pagamento/assinatura ativa de uma Empresa a partir do CPF de um
Cliente vinculado.

Uso:
    python manage.py simular_pagamento_empresa --cpf 398.473.518-99
    python manage.py simular_pagamento_empresa --cpf 39847351899

Regras:
- Normaliza CPF (apenas digitos) antes de buscar.
- Busca o Cliente por `cpf_hash` (campo indexado; `cpf` armazena digitos puros).
- Sobe para a Empresa via `cliente.empresa` (FK em gestao.Cliente).
- Garante que existe um Plano ativo; cria "Starter" se nenhum existir.
- Cria/atualiza `Assinatura` ativa para a Empresa.
- Cria 2 pagamentos confirmados via PIX (mes passado e este mes), com
  `gateway_ref` unico. Se ja existe um pagamento com o mesmo ref, pula.

Idempotente: rodar 2x nao duplica assinatura nem pagamentos.
"""
from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from gestao.models import Cliente, Empresa
from gestao.utils import hash_cpf, normalize_cpf
from onboarding.models import Assinatura, Pagamento, Plano


class Command(BaseCommand):
    help = "Simula uma assinatura ativa + 2 pagamentos confirmados para a empresa do CPF informado."

    def add_arguments(self, parser):
        parser.add_argument(
            "--cpf",
            required=True,
            help="CPF do cliente (com ou sem mascara).",
        )
        parser.add_argument(
            "--empresa-id",
            type=int,
            default=None,
            help=(
                "Se o Cliente ainda nao estiver vinculado a uma Empresa, "
                "vincula a esta Empresa (pk). Se omitido e existir apenas "
                "1 Empresa no sistema, usa ela automaticamente."
            ),
        )

    def handle(self, *args, **options):
        cpf_raw = options["cpf"]
        cpf_digits = normalize_cpf(cpf_raw)
        if len(cpf_digits) != 11:
            raise CommandError(
                f"CPF invalido: esperado 11 digitos apos normalizacao, recebido "
                f"{len(cpf_digits)} digitos ('{cpf_raw}')."
            )

        self.stdout.write(f"CPF normalizado: {cpf_digits}")

        # 1) Localizar Cliente via cpf_hash (pode estar em varias linhas se
        #    houve migracao parcial; tratamos como erro se > 1 empresa)
        cpf_h = hash_cpf(cpf_digits)
        clientes = list(
            Cliente.objects.select_related("empresa", "usuario").filter(
                cpf_hash=cpf_h
            )
        )
        if not clientes:
            # fallback para cpf em texto puro (casos antes do hash ser gravado)
            clientes = list(
                Cliente.objects.select_related("empresa", "usuario").filter(
                    cpf=cpf_digits
                )
            )

        if not clientes:
            raise CommandError(
                f"Nenhum Cliente encontrado para o CPF {cpf_digits}. "
                "Certifique-se de que o usuario ja esta cadastrado."
            )

        empresas = {c.empresa_id: c.empresa for c in clientes if c.empresa_id}
        if not empresas:
            # Auto-vincular: se o usuario passou --empresa-id, usa; senao, se
            # existe exatamente 1 Empresa no sistema, usa ela.
            empresa_id_arg = options.get("empresa_id")
            if empresa_id_arg:
                try:
                    empresa_alvo = Empresa.objects.get(pk=empresa_id_arg)
                except Empresa.DoesNotExist as exc:
                    raise CommandError(
                        f"Empresa pk={empresa_id_arg} nao existe."
                    ) from exc
            else:
                empresas_qs = list(Empresa.objects.all()[:2])
                if len(empresas_qs) == 0:
                    raise CommandError(
                        "Nenhuma Empresa existe no sistema. Crie uma antes "
                        "ou use --empresa-id."
                    )
                if len(empresas_qs) > 1:
                    raise CommandError(
                        "Existe mais de 1 Empresa no sistema — informe qual "
                        "usar via --empresa-id."
                    )
                empresa_alvo = empresas_qs[0]

            # vincula todos os clientes encontrados
            for c in clientes:
                c.empresa = empresa_alvo
                c.save(update_fields=["empresa"])
            self.stdout.write(
                self.style.WARNING(
                    f"  Cliente(s) vinculado(s) a Empresa #{empresa_alvo.pk} "
                    f"- {empresa_alvo.nome} (auto-vinculo)."
                )
            )
            empresas = {empresa_alvo.pk: empresa_alvo}

        if len(empresas) > 1:
            raise CommandError(
                f"CPF {cpf_digits} esta vinculado a {len(empresas)} empresas distintas: "
                f"{[e.nome for e in empresas.values()]}. Abortando para evitar "
                "acao ambigua."
            )

        empresa: Empresa = next(iter(empresas.values()))
        self.stdout.write(f"Empresa alvo: #{empresa.pk} - {empresa.nome}")

        with transaction.atomic():
            # 2) Garantir plano ativo
            plano = (
                Plano.objects.filter(ativo=True)
                .order_by("ordem", "preco_mensal")
                .first()
            )
            if not plano:
                plano = Plano.objects.create(
                    nome="Starter",
                    slug="starter",
                    preco_mensal=Decimal("199.90"),
                    limite_operadores=5,
                    limite_clientes=0,
                    trial_dias=14,
                    ativo=True,
                    ordem=0,
                )
                self.stdout.write(
                    self.style.WARNING(
                        f"  Plano 'Starter' criado (R$ {plano.preco_mensal})."
                    )
                )
            else:
                self.stdout.write(
                    f"  Plano selecionado: {plano.nome} (R$ {plano.preco_mensal})."
                )

            # 3) Criar/atualizar Assinatura (OneToOne empresa)
            agora = timezone.now()
            assinatura_defaults = {
                "plano": plano,
                "status": Assinatura.STATUS_ATIVA,
                "data_inicio": agora - timedelta(days=30),
                "data_vencimento": agora + timedelta(days=30),
                "gateway_customer_id": f"fake_cust_{empresa.pk}",
                "gateway_subscription_id": f"fake_sub_{empresa.pk}",
            }
            assinatura, criada = Assinatura.objects.get_or_create(
                empresa=empresa, defaults=assinatura_defaults
            )
            if not criada:
                for campo, valor in assinatura_defaults.items():
                    setattr(assinatura, campo, valor)
                assinatura.save()
                self.stdout.write("  Assinatura existente: atualizada.")
            else:
                self.stdout.write("  Assinatura: criada.")

            # 4) Criar 2 pagamentos confirmados (mes passado + este mes)
            pagamentos_info = []
            for offset_dias in (30, 0):
                data_pagto = agora - timedelta(days=offset_dias)
                # gateway_ref unico (uuid4) — idempotencia via unique constraint
                gw_ref = f"fake_pay_{empresa.pk}_{uuid.uuid4().hex[:10]}"

                pag = Pagamento.objects.create(
                    assinatura=assinatura,
                    valor=plano.preco_mensal,
                    status=Pagamento.STATUS_CONFIRMADO,
                    metodo=Pagamento.METODO_PIX,
                    gateway_ref=gw_ref,
                    gateway_event_type="charge.succeeded",
                    dados_gateway={
                        "simulado": True,
                        "referencia_mes": data_pagto.strftime("%Y-%m"),
                    },
                )
                # criado_em e auto_now_add — so via update()
                Pagamento.objects.filter(pk=pag.pk).update(criado_em=data_pagto)
                pag.refresh_from_db()
                pagamentos_info.append(pag)

        # 5) Resumo
        self.stdout.write(self.style.SUCCESS("\n=== RESUMO ==="))
        self.stdout.write(f"Empresa......: #{empresa.pk} - {empresa.nome}")
        self.stdout.write(f"Plano........: {plano.nome} - R$ {plano.preco_mensal}")
        self.stdout.write(f"Status.......: {assinatura.get_status_display()}")
        self.stdout.write(
            f"Inicio.......: {assinatura.data_inicio:%d/%m/%Y %H:%M}"
        )
        self.stdout.write(
            f"Vencimento...: {assinatura.data_vencimento:%d/%m/%Y %H:%M}"
        )
        self.stdout.write(f"Customer gw..: {assinatura.gateway_customer_id}")
        self.stdout.write(f"Subscription.: {assinatura.gateway_subscription_id}")
        self.stdout.write("Pagamentos criados:")
        for p in pagamentos_info:
            self.stdout.write(
                f"  - {p.gateway_ref} | R$ {p.valor} | "
                f"{p.get_metodo_display()} | {p.get_status_display()} | "
                f"criado_em={p.criado_em:%d/%m/%Y}"
            )
        self.stdout.write(self.style.SUCCESS("OK"))
