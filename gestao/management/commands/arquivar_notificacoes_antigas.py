"""Arquiva notificações já lidas cujo criado_em seja anterior a N dias.

Uso manual:
    python manage.py arquivar_notificacoes_antigas
    python manage.py arquivar_notificacoes_antigas --dias 45
    python manage.py arquivar_notificacoes_antigas --dry-run

Agendamento (Railway cron):
    0 3 * * * python manage.py arquivar_notificacoes_antigas
"""
from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from gestao.models import NotificacaoSistema


class Command(BaseCommand):
    help = "Arquiva notificações já lidas mais antigas que X dias (default 30)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dias",
            type=int,
            default=30,
            help="Número de dias de corte (default: 30).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só mostra quantas notificações seriam arquivadas, sem gravar.",
        )

    def handle(self, *args, **options):
        dias = options["dias"]
        dry_run = options["dry_run"]
        agora = timezone.now()
        limite = agora - timedelta(days=dias)

        qs = NotificacaoSistema.objects.filter(
            arquivada_em__isnull=True,
            lida=True,
            criado_em__lt=limite,
        )
        total = qs.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"[dry-run] {total} notificação(ões) seriam arquivadas (criado_em < {limite.isoformat()})."
                )
            )
            return

        arquivadas = NotificacaoSistema.arquivar_antigas(dias=dias, agora=agora)
        self.stdout.write(
            self.style.SUCCESS(
                f"{arquivadas} notificação(ões) arquivadas. Corte: criado_em < {limite.isoformat()}."
            )
        )
