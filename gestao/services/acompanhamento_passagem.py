import logging
from dataclasses import dataclass

from django.utils import timezone

from gestao.models import AcompanhamentoPassagem, HistoricoVerificacao
from gestao.services.monitoring import comparar_resultado, criar_notificacao_mudanca
from gestao.services.scrapers import get_scraper
from gestao.services.scrapers.base import ScraperError

logger = logging.getLogger(__name__)


@dataclass
class AcompanhamentoSyncResult:
    success: bool
    message: str


def _extract_last_name_from_text(value):
    parts = [part for part in (value or "").strip().split() if part]
    return parts[-1] if parts else ""


def ensure_acompanhamento_passagem(emissao):
    cliente_usuario = getattr(getattr(emissao, "cliente", None), "usuario", None)
    defaults = {
        "modo_consulta": (
            AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA
            if getattr(getattr(emissao, "companhia_aerea", None), "site_url", "")
            else AcompanhamentoPassagem.MODO_MANUAL
        ),
        "localizador_consulta": emissao.localizador or "",
        "status_reserva": (
            AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO
            if emissao.localizador
            else AcompanhamentoPassagem.STATUS_RESERVA_NAO_INICIADO
        ),
        "status_voo": AcompanhamentoPassagem.STATUS_VOO_NAO_CONSULTADO,
    }
    acompanhamento, _ = AcompanhamentoPassagem.objects.get_or_create(
        emissao=emissao,
        defaults=defaults,
    )

    updated_fields = []
    if not acompanhamento.localizador_consulta and emissao.localizador:
        acompanhamento.localizador_consulta = emissao.localizador
        updated_fields.append("localizador_consulta")
    if not acompanhamento.sobrenome_consulta:
        primeiro_passageiro = emissao.passageiros.order_by("id").first()
        nome_base = getattr(primeiro_passageiro, "nome", "") or (
            cliente_usuario.get_full_name() or cliente_usuario.username if cliente_usuario else ""
        )
        sobrenome = _extract_last_name_from_text(nome_base)
        if sobrenome:
            acompanhamento.sobrenome_consulta = sobrenome
            updated_fields.append("sobrenome_consulta")
    if (
        acompanhamento.modo_consulta == AcompanhamentoPassagem.MODO_MANUAL
        and getattr(getattr(emissao, "companhia_aerea", None), "site_url", "")
    ):
        acompanhamento.modo_consulta = AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA
        updated_fields.append("modo_consulta")
    if updated_fields:
        acompanhamento.save(update_fields=updated_fields + ["atualizado_em"])
    return acompanhamento


def _reservation_tone(status):
    if status in {
        AcompanhamentoPassagem.STATUS_RESERVA_EMITIDO,
        AcompanhamentoPassagem.STATUS_RESERVA_TICKETADO,
        AcompanhamentoPassagem.STATUS_RESERVA_EMBARCADO,
        AcompanhamentoPassagem.STATUS_RESERVA_CONCLUIDO,
    }:
        return "success"
    if status in {
        AcompanhamentoPassagem.STATUS_RESERVA_ALTERADO,
        AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE,
        AcompanhamentoPassagem.STATUS_RESERVA_AGUARDANDO,
    }:
        return "warning"
    if status == AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO:
        return "danger"
    return "muted"


def build_acompanhamento_summary(acompanhamento):
    if not acompanhamento:
        return None
    emissao = getattr(acompanhamento, "emissao", None)
    companhia = getattr(emissao, "companhia_aerea", None)
    codigo_companhia = (
        companhia.codigo_normalizado() if companhia and hasattr(companhia, "codigo_normalizado") else ""
    )
    rotulo_codigo_reserva = (
        getattr(companhia, "rotulo_codigo_reserva", "") or "Localizador / Código da Reserva"
    )
    eh_latam = codigo_companhia == "LATAM"
    return {
        "modo_label": acompanhamento.get_modo_consulta_display(),
        "status_reserva_label": acompanhamento.get_status_reserva_display(),
        "status_voo_label": acompanhamento.get_status_voo_display(),
        "reserva_tone": _reservation_tone(acompanhamento.status_reserva),
        "ultima_sincronizacao_display": (
            timezone.localtime(acompanhamento.ultima_sincronizacao_em).strftime("%d/%m/%Y %H:%M")
            if acompanhamento.ultima_sincronizacao_em
            else "Nao sincronizado"
        ),
        "proxima_verificacao_display": (
            timezone.localtime(acompanhamento.proxima_verificacao_em).strftime("%d/%m/%Y %H:%M")
            if acompanhamento.proxima_verificacao_em
            else "Sem agendamento"
        ),
        "resumo": acompanhamento.ultimo_resumo or "Sem retorno consolidado ainda.",
        "erro": acompanhamento.ultimo_erro or "",
        "ativo": acompanhamento.ativo,
        # Identificadores: para LATAM separamos Nº da Ordem (orderId) e
        # Código da Reserva (reloc / PNR). Para outras companhias mantemos
        # um único campo "Localizador / Código da Reserva".
        "eh_latam": eh_latam,
        "rotulo_codigo_reserva": rotulo_codigo_reserva,
        "codigo_reserva_portal": acompanhamento.codigo_reserva_portal or "",
        "numero_ordem": acompanhamento.localizador_consulta or (getattr(emissao, "localizador", "") or ""),
    }


class BaseAcompanhamentoProvider:
    provider_key = AcompanhamentoPassagem.MODO_MANUAL

    def sync(self, acompanhamento):
        raise NotImplementedError


class ManualAcompanhamentoProvider(BaseAcompanhamentoProvider):
    provider_key = AcompanhamentoPassagem.MODO_MANUAL

    def sync(self, acompanhamento):
        acompanhamento.ultima_sincronizacao_em = timezone.now()
        acompanhamento.ultimo_erro = ""
        if not acompanhamento.ultimo_resumo:
            acompanhamento.ultimo_resumo = (
                "Acompanhamento mantido manualmente. Atualize os status conforme o retorno operacional."
            )
        acompanhamento.save(
            update_fields=[
                "ultima_sincronizacao_em",
                "ultimo_erro",
                "ultimo_resumo",
                "atualizado_em",
            ]
        )
        return AcompanhamentoSyncResult(
            success=True,
            message="Acompanhamento atualizado manualmente com sucesso.",
        )


class PlaceholderAcompanhamentoProvider(BaseAcompanhamentoProvider):
    def sync(self, acompanhamento):
        acompanhamento.ultima_sincronizacao_em = timezone.now()
        if not acompanhamento.localizador_consulta:
            acompanhamento.ultimo_erro = "Informe o localizador antes de tentar consultar o status automaticamente."
            acompanhamento.save(
                update_fields=["ultima_sincronizacao_em", "ultimo_erro", "atualizado_em"]
            )
            return AcompanhamentoSyncResult(
                success=False,
                message="Falta o localizador para iniciar a consulta automatica.",
            )
        if self.provider_key == AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA and not acompanhamento.sobrenome_consulta:
            acompanhamento.ultimo_erro = "Informe o sobrenome do passageiro para consultas no portal da companhia."
            acompanhamento.save(
                update_fields=["ultima_sincronizacao_em", "ultimo_erro", "atualizado_em"]
            )
            return AcompanhamentoSyncResult(
                success=False,
                message="Falta o sobrenome do passageiro para a consulta no portal da companhia.",
            )

        acompanhamento.ultimo_erro = (
            "Conector automatico ainda nao foi implementado para este modo de consulta. "
            "A base ja ficou pronta para receber a integracao."
        )
        if not acompanhamento.ultimo_resumo:
            acompanhamento.ultimo_resumo = (
                "Registro preparado para sincronizacao futura. Enquanto isso, mantenha o status atualizado manualmente."
            )
        acompanhamento.save(
            update_fields=[
                "ultima_sincronizacao_em",
                "ultimo_erro",
                "ultimo_resumo",
                "atualizado_em",
            ]
        )
        return AcompanhamentoSyncResult(
            success=False,
            message="A estrutura ficou pronta, mas o conector automatico ainda nao foi implementado.",
        )


class PortalCompanhiaScraperProvider(BaseAcompanhamentoProvider):
    """Roda o scraper específico da companhia, grava histórico e dispara alerta."""

    provider_key = AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA

    def sync(self, acompanhamento):
        emissao = acompanhamento.emissao
        companhia = getattr(emissao, "companhia_aerea", None)
        codigo = companhia.codigo_normalizado() if companhia else ""
        scraper = get_scraper(codigo) if codigo else None

        if not scraper:
            return PlaceholderAcompanhamentoProvider().sync(acompanhamento)

        if not acompanhamento.localizador_consulta:
            acompanhamento.ultimo_erro = (
                "Informe o localizador antes de tentar consultar o status automaticamente."
            )
            acompanhamento.ultima_sincronizacao_em = timezone.now()
            acompanhamento.save(
                update_fields=[
                    "ultimo_erro",
                    "ultima_sincronizacao_em",
                    "atualizado_em",
                ]
            )
            return AcompanhamentoSyncResult(
                success=False,
                message="Falta o localizador para iniciar a consulta automatica.",
            )
        if not acompanhamento.sobrenome_consulta:
            acompanhamento.ultimo_erro = (
                "Informe o sobrenome do passageiro antes de consultar o portal da companhia."
            )
            acompanhamento.ultima_sincronizacao_em = timezone.now()
            acompanhamento.save(
                update_fields=[
                    "ultimo_erro",
                    "ultima_sincronizacao_em",
                    "atualizado_em",
                ]
            )
            return AcompanhamentoSyncResult(
                success=False,
                message="Falta o sobrenome do passageiro para a consulta.",
            )

        historico = HistoricoVerificacao(
            acompanhamento=acompanhamento,
            scraper_nome=codigo,
            status_reserva_anterior=acompanhamento.status_reserva or "",
            status_voo_anterior=acompanhamento.status_voo or "",
        )

        try:
            resultado = scraper.consultar(
                acompanhamento.localizador_consulta,
                acompanhamento.sobrenome_consulta,
                url=getattr(companhia, "site_url", "") or "",
            )
        except ScraperError as exc:
            mensagem = str(exc)
            historico.sucesso = False
            historico.erro_mensagem = mensagem
            historico.save()
            acompanhamento.ultimo_erro = mensagem
            acompanhamento.ultima_sincronizacao_em = timezone.now()
            acompanhamento.save(
                update_fields=[
                    "ultimo_erro",
                    "ultima_sincronizacao_em",
                    "atualizado_em",
                ]
            )
            return AcompanhamentoSyncResult(success=False, message=mensagem)

        mudanca = comparar_resultado(acompanhamento, resultado)

        historico.sucesso = True
        historico.duracao_ms = resultado.duracao_ms
        historico.payload_sanitizado = resultado.payload_sanitizado
        historico.status_reserva_novo = resultado.status_reserva
        historico.status_voo_novo = resultado.status_voo
        historico.mudou_desde_anterior = mudanca.mudou

        notificacao_enviada = False
        if mudanca.mudou and mudanca.relevante_para_passageiro:
            try:
                notificacao_enviada = criar_notificacao_mudanca(acompanhamento, mudanca)
            except Exception:
                logger.exception(
                    "Falha inesperada ao criar notificacao no portal para emissao %s",
                    emissao.id,
                )
        historico.notificacao_disparada = notificacao_enviada
        historico.save()

        acompanhamento.status_reserva = resultado.status_reserva
        acompanhamento.status_voo = resultado.status_voo
        acompanhamento.payload_bruto_json = resultado.payload_sanitizado or {}
        acompanhamento.ultimo_resumo = resultado.resumo or acompanhamento.ultimo_resumo
        acompanhamento.ultimo_erro = ""
        acompanhamento.ultima_sincronizacao_em = timezone.now()

        update_fields = [
            "status_reserva",
            "status_voo",
            "payload_bruto_json",
            "ultimo_resumo",
            "ultimo_erro",
            "ultima_sincronizacao_em",
            "atualizado_em",
        ]
        # Reloc devolvido pelo scraper (ex.: LATAM expõe `_reloc` = PNR de 6
        # dígitos enquanto `localizador_consulta` guarda o orderId LA…IWSR).
        reloc = (resultado.payload_sanitizado or {}).get("_reloc") or ""
        if reloc and reloc != acompanhamento.codigo_reserva_portal:
            acompanhamento.codigo_reserva_portal = reloc[:24]
            update_fields.append("codigo_reserva_portal")

        acompanhamento.save(update_fields=update_fields)

        if mudanca.mudou:
            base = f"Status atualizado ({mudanca.resumo_humano()})."
            if mudanca.relevante_para_passageiro:
                if notificacao_enviada:
                    return AcompanhamentoSyncResult(
                        success=True,
                        message=f"{base} Alerta criado no painel do operador.",
                    )
                return AcompanhamentoSyncResult(
                    success=True,
                    message=f"{base} Não foi possível registrar alerta no painel.",
                )
            return AcompanhamentoSyncResult(success=True, message=base)
        return AcompanhamentoSyncResult(
            success=True, message="Consulta concluida. Nenhuma mudanca detectada."
        )


PROVIDERS = {
    AcompanhamentoPassagem.MODO_MANUAL: ManualAcompanhamentoProvider(),
    AcompanhamentoPassagem.MODO_SISTEMA_ORIGEM: PlaceholderAcompanhamentoProvider(),
    AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA: PortalCompanhiaScraperProvider(),
    AcompanhamentoPassagem.MODO_API_VOO: PlaceholderAcompanhamentoProvider(),
}


def sync_acompanhamento_passagem(acompanhamento):
    provider = PROVIDERS.get(
        acompanhamento.modo_consulta,
        PROVIDERS[AcompanhamentoPassagem.MODO_MANUAL],
    )
    provider.provider_key = acompanhamento.modo_consulta
    return provider.sync(acompanhamento)
