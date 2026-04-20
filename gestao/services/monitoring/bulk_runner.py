"""Roda atualizações em massa em background, isoladas por empresa.

Decisões:
- Threading puro (sem Celery/Redis): Railway Hobby suporta 8 vCPUs e o trabalho
  é I/O-bound (espera de scraper). ThreadPool=10 + rate limiter por companhia
  satura bem a banda sem PSU de operação adicional.
- Tenant isolation: a queryset SEMPRE passa por ``da_empresa(empresa)``. Nunca
  recebemos lista de IDs externos — a empresa é resolvida no servidor.
- Debounce: 1 dispatch ativo por empresa por vez (lock no cache). Operador que
  clica 5x não cria 5 jobs — recebe o job em andamento.
- Hard cap: ``MAX_PASSAGENS_POR_DISPATCH`` evita que um clique acidente uma
  empresa enorme e segure o pool por horas.
"""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import timedelta
from typing import Iterable

from django.core.cache import cache
from django.db import close_old_connections, transaction
from django.utils import timezone

from gestao.models import (
    AcompanhamentoPassagem,
    AtualizacaoEmMassa,
    Empresa,
)
from gestao.services.acompanhamento_passagem import sync_acompanhamento_passagem
from gestao.services.monitoring.rate_limiter import (
    RateLimitTimeout,
    acquire as acquire_rate_limit,
)

logger = logging.getLogger(__name__)


MAX_PASSAGENS_POR_DISPATCH = 1000
THREAD_POOL_SIZE = 10
DEBOUNCE_SEGUNDOS = 60
JOB_TIMEOUT_MINUTOS = 10


def _debounce_key(empresa_id: int) -> str:
    return f"atualizacao_em_massa:lock:{empresa_id}"


def _registrar_lock(empresa_id: int, job_id: int) -> bool:
    """Registra lock atômico no cache. Retorna False se já existe."""
    return cache.add(_debounce_key(empresa_id), job_id, timeout=DEBOUNCE_SEGUNDOS)


def _liberar_lock(empresa_id: int) -> None:
    cache.delete(_debounce_key(empresa_id))


def _job_em_andamento_para(empresa_id: int) -> AtualizacaoEmMassa | None:
    return (
        AtualizacaoEmMassa.objects.filter(
            empresa_id=empresa_id,
            status=AtualizacaoEmMassa.STATUS_EM_ANDAMENTO,
        )
        .order_by("-iniciado_em")
        .first()
    )


@dataclass
class DispatchResultado:
    job: AtualizacaoEmMassa
    aceito: bool
    motivo: str = ""


def disparar_atualizacao_em_massa(
    empresa: Empresa,
    *,
    iniciado_por=None,
    apenas_companhia_codigo: str | None = None,
) -> DispatchResultado:
    """Cria o registro de job e inicia thread em background.

    A view chama isto e retorna imediatamente o ``job_id`` pro frontend
    iniciar polling. Se houver dispatch ativo recente da mesma empresa,
    devolve esse mesmo job (debounce — protege contra duplo-clique).
    """
    if not empresa or not empresa.pk:
        raise ValueError("Empresa obrigatória para isolamento tenant.")

    em_andamento = _job_em_andamento_para(empresa.pk)
    if em_andamento:
        return DispatchResultado(
            job=em_andamento,
            aceito=False,
            motivo="Já existe uma atualização em andamento para essa empresa.",
        )

    queryset = (
        AcompanhamentoPassagem.objects.da_empresa(empresa)
        .ativas()
        .com_voo_futuro()
        .select_related(
            "emissao__companhia_aerea",
            "emissao__cliente__usuario",
            "emissao__cliente__empresa",
            "emissao__conta_administrada",
        )
    )
    if apenas_companhia_codigo:
        queryset = queryset.filter(
            emissao__companhia_aerea__codigo__iexact=apenas_companhia_codigo
        )

    ids = list(queryset.values_list("id", flat=True)[:MAX_PASSAGENS_POR_DISPATCH])

    with transaction.atomic():
        job = AtualizacaoEmMassa.objects.create(
            empresa=empresa,
            iniciado_por=iniciado_por if getattr(iniciado_por, "pk", None) else None,
            total=len(ids),
            status=AtualizacaoEmMassa.STATUS_EM_ANDAMENTO,
        )

    if not _registrar_lock(empresa.pk, job.pk):
        # Race: outro thread cadastrou o lock antes. Marcamos esse job como
        # interrompido pra não confundir o operador.
        job.status = AtualizacaoEmMassa.STATUS_INTERROMPIDO
        job.mensagem_erro = "Outra atualização foi disparada simultaneamente."
        job.concluido_em = timezone.now()
        job.save(update_fields=["status", "mensagem_erro", "concluido_em"])
        em_andamento = _job_em_andamento_para(empresa.pk) or job
        return DispatchResultado(
            job=em_andamento,
            aceito=False,
            motivo="Já existe uma atualização em andamento para essa empresa.",
        )

    if not ids:
        job.status = AtualizacaoEmMassa.STATUS_CONCLUIDO
        job.concluido_em = timezone.now()
        job.save(update_fields=["status", "concluido_em"])
        _liberar_lock(empresa.pk)
        return DispatchResultado(
            job=job,
            aceito=True,
            motivo="Nenhuma passagem com voo futuro encontrada.",
        )

    thread = threading.Thread(
        target=_executar_job,
        args=(job.pk, empresa.pk, ids),
        name=f"atualizacao-em-massa-{job.pk}",
        daemon=True,
    )
    thread.start()
    return DispatchResultado(job=job, aceito=True)


def _executar_job(job_id: int, empresa_id: int, ids: Iterable[int]) -> None:
    """Executa o job inteiro fora do request/response cycle.

    Cuidados:
    - Cada thread fecha conexões antigas pra não vazar (Django default).
    - Atualiza contadores no banco a cada N processados pra UI poder polling.
    - Captura qualquer exceção pra não morrer silenciosamente em background.
    """
    try:
        ids_lista = list(ids)
        with ThreadPoolExecutor(max_workers=THREAD_POOL_SIZE, thread_name_prefix=f"job{job_id}") as pool:
            futures = {
                pool.submit(_processar_um, job_id, empresa_id, acomp_id): acomp_id
                for acomp_id in ids_lista
            }
            processados = 0
            for future in as_completed(futures):
                processados += 1
                try:
                    future.result()
                except Exception:
                    logger.exception("Falha em item do job %s", job_id)
                if processados % 5 == 0:
                    _persistir_progresso(job_id)
        _finalizar_job(job_id, status=AtualizacaoEmMassa.STATUS_CONCLUIDO)
    except Exception as exc:
        logger.exception("Falha geral no job %s", job_id)
        _finalizar_job(
            job_id,
            status=AtualizacaoEmMassa.STATUS_ERRO,
            mensagem_erro=str(exc)[:500],
        )
    finally:
        _liberar_lock(empresa_id)
        close_old_connections()


def _processar_um(job_id: int, empresa_id: int, acompanhamento_id: int) -> None:
    """Processa uma única passagem. Roda dentro do ThreadPool.

    Validamos o tenant DENTRO da thread também (defesa em profundidade contra
    race entre snapshot dos IDs e execução).
    """
    try:
        acompanhamento = (
            AcompanhamentoPassagem.objects.select_related(
                "emissao__companhia_aerea",
                "emissao__cliente__empresa",
                "emissao__conta_administrada__empresa",
                "emissao__emissor_parceiro__empresa",
            )
            .filter(id=acompanhamento_id)
            .first()
        )
        if not acompanhamento:
            _registrar_resultado_item(
                job_id,
                identificador=str(acompanhamento_id),
                status="erro",
                detalhe="Passagem removida durante a atualização.",
            )
            return

        if not _pertence_a_empresa(acompanhamento, empresa_id):
            logger.warning(
                "Tenant violation evitada: acomp %s não pertence a empresa %s",
                acompanhamento_id,
                empresa_id,
            )
            _registrar_resultado_item(
                job_id,
                identificador=str(acompanhamento_id),
                status="erro",
                detalhe="Passagem fora do tenant.",
            )
            return

        codigo_cia = ""
        cia = getattr(acompanhamento.emissao, "companhia_aerea", None)
        if cia:
            try:
                codigo_cia = cia.codigo_normalizado() or ""
            except Exception:
                codigo_cia = ""

        antes_reserva = acompanhamento.get_status_reserva_display()
        antes_voo = acompanhamento.get_status_voo_display()

        try:
            with acquire_rate_limit(codigo_cia):
                resultado = sync_acompanhamento_passagem(acompanhamento)
        except RateLimitTimeout as exc:
            _registrar_resultado_item(
                job_id,
                identificador=acompanhamento.localizador_consulta or str(acompanhamento_id),
                status="erro",
                detalhe=str(exc),
            )
            _incrementar_contador(job_id, "erro")
            return
        except Exception as exc:
            logger.exception("Erro inesperado processando acomp %s", acompanhamento_id)
            _registrar_resultado_item(
                job_id,
                identificador=acompanhamento.localizador_consulta or str(acompanhamento_id),
                status="erro",
                detalhe=str(exc)[:200],
            )
            _incrementar_contador(job_id, "erro")
            return

        acompanhamento.refresh_from_db()
        depois_reserva = acompanhamento.get_status_reserva_display()
        depois_voo = acompanhamento.get_status_voo_display()
        mudou_reserva = antes_reserva != depois_reserva
        mudou_voo = antes_voo != depois_voo
        teve_mudanca = mudou_reserva or mudou_voo

        if not resultado.success:
            _registrar_resultado_item(
                job_id,
                identificador=acompanhamento.localizador_consulta or str(acompanhamento_id),
                status="erro",
                detalhe=resultado.message,
            )
            _incrementar_contador(job_id, "erro")
            return

        _registrar_resultado_item(
            job_id,
            identificador=acompanhamento.localizador_consulta or str(acompanhamento_id),
            status="mudanca" if teve_mudanca else "ok",
            detalhe=(
                f"{antes_reserva} → {depois_reserva}"
                if teve_mudanca
                else "OK"
            ),
            extra={
                "voo_antes": antes_voo,
                "voo_depois": depois_voo,
                "reserva_antes": antes_reserva,
                "reserva_depois": depois_reserva,
            },
        )
        if teve_mudanca:
            _incrementar_contador(job_id, "com_mudanca")
        else:
            _incrementar_contador(job_id, "sem_mudanca")
        _incrementar_contador(job_id, "ok")
    finally:
        close_old_connections()


def _pertence_a_empresa(acompanhamento: AcompanhamentoPassagem, empresa_id: int) -> bool:
    emissao = acompanhamento.emissao
    candidatas = (
        getattr(getattr(emissao, "cliente", None), "empresa_id", None),
        getattr(getattr(emissao, "conta_administrada", None), "empresa_id", None),
        getattr(getattr(emissao, "emissor_parceiro", None), "empresa_id", None),
    )
    return empresa_id in candidatas


def _registrar_resultado_item(job_id: int, *, identificador: str, status: str, detalhe: str, extra: dict | None = None) -> None:
    item = {
        "ref": identificador,
        "status": status,
        "detalhe": detalhe,
    }
    if extra:
        item.update({k: v for k, v in extra.items() if v is not None})
    with transaction.atomic():
        job = AtualizacaoEmMassa.objects.select_for_update().get(pk=job_id)
        if not isinstance(job.resultado, list):
            job.resultado = []
        job.resultado.append(item)
        # Limita a lista pra não estourar JSON gigante (1000 hard-cap).
        if len(job.resultado) > MAX_PASSAGENS_POR_DISPATCH:
            job.resultado = job.resultado[-MAX_PASSAGENS_POR_DISPATCH:]
        job.save(update_fields=["resultado"])


def _incrementar_contador(job_id: int, campo: str) -> None:
    with transaction.atomic():
        job = AtualizacaoEmMassa.objects.select_for_update().get(pk=job_id)
        atual = getattr(job, campo, 0)
        setattr(job, campo, atual + 1)
        job.save(update_fields=[campo])


def _persistir_progresso(job_id: int) -> None:
    # Já gravamos a cada item; este hook serve pra futuro (ex.: notificação WS).
    pass


def _finalizar_job(job_id: int, *, status: str, mensagem_erro: str = "") -> None:
    with transaction.atomic():
        job = AtualizacaoEmMassa.objects.select_for_update().get(pk=job_id)
        job.status = status
        job.concluido_em = timezone.now()
        if mensagem_erro:
            job.mensagem_erro = mensagem_erro
        job.save(update_fields=["status", "concluido_em", "mensagem_erro"])


def marcar_jobs_orfaos(*, timeout_minutos: int = JOB_TIMEOUT_MINUTOS) -> int:
    """Marca como interrompidos os jobs que ficaram parados (deploy/crash).

    Roda no cron a cada minuto. Retorna a quantidade marcada.
    """
    limite = timezone.now() - timedelta(minutes=timeout_minutos)
    qs = AtualizacaoEmMassa.objects.filter(
        status=AtualizacaoEmMassa.STATUS_EM_ANDAMENTO,
        iniciado_em__lt=limite,
    )
    quantidade = qs.update(
        status=AtualizacaoEmMassa.STATUS_INTERROMPIDO,
        concluido_em=timezone.now(),
        mensagem_erro="Job interrompido por timeout (provavelmente deploy ou crash).",
    )
    return quantidade
