from io import BytesIO
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm


def gerar_pdf_emissao(emissao):
    """Gera um PDF simples com os dados de uma EmissaoPassagem."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    # Cabeçalho
    elements.append(Paragraph("Detalhamento de Emissão de Passagem Aérea", styles["Title"]))
    elements.append(Paragraph(timezone.now().strftime("%d/%m/%Y %H:%M"), styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Dados gerais
    dados = [
        ["Passageiro", emissao.cliente.usuario.get_full_name() or emissao.cliente.usuario.username],
        ["Documento", emissao.cliente.cpf],
        ["Localizador", emissao.localizador],
        ["Companhia", emissao.companhia_aerea],
        ["Data Emissão", emissao.data_ida.strftime("%d/%m/%Y")],
        ["Valor Total", f"R$ {emissao.valor_pago:.2f}"],
    ]
    table = Table(dados, colWidths=[5 * cm, 11 * cm])
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 12))

    # Informações do voo
    voo = [
        ["Origem", str(emissao.aeroporto_partida)],
        ["Destino", str(emissao.aeroporto_destino)],
        ["Data Ida", emissao.data_ida.strftime("%d/%m/%Y")],
        ["Data Volta", emissao.data_volta.strftime("%d/%m/%Y") if emissao.data_volta else "-"],
        ["Programa", emissao.programa.nome if emissao.programa else "-"],
        ["Passageiros", emissao.qtd_passageiros],
    ]
    table_voo = Table(voo, colWidths=[5 * cm, 11 * cm])
    table_voo.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    elements.append(table_voo)
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("Documento gerado automaticamente – não utilize como cartão de embarque", styles["Normal"]))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def gerar_pdf_cotacao(cotacao):
    """Gera um PDF detalhado com as informações de uma CotacaoVoo."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )
    styles = getSampleStyleSheet()
    elements = []

    # Cabeçalho
    elements.append(Paragraph("Cotação de Passagem Aérea", styles["Title"]))
    elements.append(Paragraph(timezone.now().strftime("%d/%m/%Y %H:%M"), styles["Normal"]))
    elements.append(Spacer(1, 12))

    # Informações do cliente e voo
    dados = [
        ["Cliente", cotacao.cliente.usuario.get_full_name() or cotacao.cliente.usuario.username],
        ["Companhia", cotacao.companhia_aerea or "-"],
        ["Origem", str(cotacao.origem) if cotacao.origem else "-"],
        ["Destino", str(cotacao.destino) if cotacao.destino else "-"],
        ["Data Ida", cotacao.data_ida.strftime("%d/%m/%Y %H:%M")],
        ["Data Volta", cotacao.data_volta.strftime("%d/%m/%Y %H:%M") if cotacao.data_volta else "-"],
        ["Programa", cotacao.programa.nome if cotacao.programa else "-"],
        ["Passageiros", cotacao.qtd_passageiros],
    ]
    table = Table(dados, colWidths=[6 * cm, 10 * cm])
    table.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    )
    elements.append(table)
    elements.append(Spacer(1, 12))

    # Detalhes de valores
    cotacao.calcular_valores()
    valor_parcela = cotacao.valor_parcelado / cotacao.parcelas if cotacao.parcelas else cotacao.valor_parcelado
    valores = [
        ["Milhas", f"{cotacao.milhas:,}".replace(",", ".")],
        ["Valor Milheiro", f"R$ {cotacao.valor_milheiro:.2f}"],
        ["Taxas", f"R$ {cotacao.taxas:.2f}"],
        ["Valor Passagem", f"R$ {cotacao.valor_passagem:.2f}"],
        ["Parcelas", f"{cotacao.parcelas}x sem juros de R$ {valor_parcela:.2f}"],
        ["Valor Parcelado", f"R$ {cotacao.valor_parcelado:.2f}"],
        ["Valor à Vista", f"R$ {cotacao.valor_vista:.2f}"],
        ["Validade", cotacao.validade.strftime("%d/%m/%Y") if cotacao.validade else "-"],
    ]
    table_val = Table(valores, colWidths=[6 * cm, 10 * cm])
    table_val.setStyle(
        TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ])
    )
    elements.append(table_val)
    elements.append(Spacer(1, 24))

    elements.append(Paragraph("Essa é uma proposta de cotação. Valores sujeitos a disponibilidade.", styles["Normal"]))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
