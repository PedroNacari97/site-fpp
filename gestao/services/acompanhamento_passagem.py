from dataclasses import dataclass

from django.utils import timezone

from gestao.models import AcompanhamentoPassagem


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


PROVIDERS = {
    AcompanhamentoPassagem.MODO_MANUAL: ManualAcompanhamentoProvider(),
    AcompanhamentoPassagem.MODO_SISTEMA_ORIGEM: PlaceholderAcompanhamentoProvider(),
    AcompanhamentoPassagem.MODO_PORTAL_COMPANHIA: PlaceholderAcompanhamentoProvider(),
    AcompanhamentoPassagem.MODO_API_VOO: PlaceholderAcompanhamentoProvider(),
}


def sync_acompanhamento_passagem(acompanhamento):
    provider = PROVIDERS.get(
        acompanhamento.modo_consulta,
        PROVIDERS[AcompanhamentoPassagem.MODO_MANUAL],
    )
    provider.provider_key = acompanhamento.modo_consulta
    return provider.sync(acompanhamento)
