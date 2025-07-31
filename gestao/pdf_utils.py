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
