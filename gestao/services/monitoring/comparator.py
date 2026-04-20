from dataclasses import dataclass

from gestao.models import AcompanhamentoPassagem
from gestao.services.scrapers.base import ResultadoScrape


@dataclass
class MudancaDetectada:
    mudou: bool
    status_reserva_anterior: str
    status_voo_anterior: str
    status_reserva_novo: str
    status_voo_novo: str
    relevante_para_passageiro: bool

    def resumo_humano(self) -> str:
        partes = []
        if self.status_reserva_anterior != self.status_reserva_novo:
            partes.append(
                f"reserva: {self.status_reserva_anterior or 'sem registro'} → {self.status_reserva_novo}"
            )
        if self.status_voo_anterior != self.status_voo_novo:
            partes.append(
                f"voo: {self.status_voo_anterior or 'sem registro'} → {self.status_voo_novo}"
            )
        return "; ".join(partes) or "sem mudanças"


_STATUS_CRITICOS_RESERVA = {
    AcompanhamentoPassagem.STATUS_RESERVA_CANCELADO,
    AcompanhamentoPassagem.STATUS_RESERVA_ALTERADO,
    AcompanhamentoPassagem.STATUS_RESERVA_INCONSISTENTE,
}

_STATUS_CRITICOS_VOO = {
    AcompanhamentoPassagem.STATUS_VOO_CANCELADO,
    AcompanhamentoPassagem.STATUS_VOO_ATRASADO,
    AcompanhamentoPassagem.STATUS_VOO_CHECKIN,
    AcompanhamentoPassagem.STATUS_VOO_EMBARQUE,
}


def comparar_resultado(acompanhamento: AcompanhamentoPassagem, resultado: ResultadoScrape) -> MudancaDetectada:
    """Compara resultado novo com o estado atual do acompanhamento.

    Considera mudança qualquer alteração nos status de reserva ou voo.
    Marca como ``relevante_para_passageiro`` apenas mudanças para estados
    que efetivamente afetam a experiência (cancelamento, alteração, atraso, check-in liberado).
    """

    reserva_anterior = acompanhamento.status_reserva or ""
    voo_anterior = acompanhamento.status_voo or ""

    mudou_reserva = reserva_anterior != resultado.status_reserva
    mudou_voo = voo_anterior != resultado.status_voo
    mudou = mudou_reserva or mudou_voo

    relevante = False
    if mudou_reserva and resultado.status_reserva in _STATUS_CRITICOS_RESERVA:
        relevante = True
    if mudou_voo and resultado.status_voo in _STATUS_CRITICOS_VOO:
        relevante = True

    return MudancaDetectada(
        mudou=mudou,
        status_reserva_anterior=reserva_anterior,
        status_voo_anterior=voo_anterior,
        status_reserva_novo=resultado.status_reserva,
        status_voo_novo=resultado.status_voo,
        relevante_para_passageiro=relevante,
    )
