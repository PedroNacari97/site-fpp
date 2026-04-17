from decimal import Decimal

from django.core.management.base import BaseCommand

from onboarding.models import Plano

PLANOS = [
    {
        "slug": "starter",
        "defaults": {
            "nome": "Starter",
            "descricao": "Para profissionais autonomos e agencias iniciantes",
            "preco_mensal": Decimal("197.00"),
            "preco_anual": Decimal("1970.00"),
            "limite_operadores": 3,
            "limite_clientes": 100,
            "features": {k: True for k in ("emissoes", "cotacoes", "clientes", "programas_fidelidade", "pdf_profissional")},
            "trial_dias": 14,
            "ativo": True,
            "destaque": False,
            "ordem": 1,
        },
    },
    {
        "slug": "profissional",
        "defaults": {
            "nome": "Profissional",
            "descricao": "Para agencias em crescimento com equipe",
            "preco_mensal": Decimal("397.00"),
            "preco_anual": Decimal("3970.00"),
            "limite_operadores": 8,
            "limite_clientes": 500,
            "features": {k: True for k in ("emissoes", "cotacoes", "clientes", "programas_fidelidade", "pdf_profissional", "multi_operador", "relatorios", "hoteis")},
            "trial_dias": 14,
            "ativo": True,
            "destaque": True,
            "ordem": 2,
        },
    },
    {
        "slug": "enterprise",
        "defaults": {
            "nome": "Enterprise",
            "descricao": "Para agencias consolidadas com operacao robusta",
            "preco_mensal": Decimal("697.00"),
            "preco_anual": Decimal("6970.00"),
            "limite_operadores": 25,
            "limite_clientes": 0,
            "features": {k: True for k in ("emissoes", "cotacoes", "clientes", "programas_fidelidade", "pdf_profissional", "multi_operador", "relatorios", "hoteis", "api_integracao", "suporte_prioritario", "marca_branca")},
            "trial_dias": 14,
            "ativo": True,
            "destaque": False,
            "ordem": 3,
        },
    },
]


class Command(BaseCommand):
    help = "Seed dos planos iniciais da plataforma NCfly (idempotente)"

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for plano_data in PLANOS:
            slug = plano_data["slug"]
            defaults = plano_data["defaults"]
            _, created = Plano.objects.update_or_create(slug=slug, defaults=defaults)

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  [CRIADO]      {defaults['nome']} \u2014 R$ {defaults['preco_mensal']}/mes"))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"  [ATUALIZADO]  {defaults['nome']} \u2014 R$ {defaults['preco_mensal']}/mes"))

        self.stdout.write("")
        self.stdout.write(f"Seed concluido: {created_count} criado(s), {updated_count} atualizado(s), {len(PLANOS)} total.")
