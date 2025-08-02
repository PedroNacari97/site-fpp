from io import BytesIO
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)


def gerar_pdf_emissao(emissao):
    """Gera um PDF com os dados de uma ``EmissaoPassagem``.

    O layout segue o mesmo padrão visual utilizado no PDF de cotação,
    mantendo margens, fontes e espaçamentos consistentes.
    """

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()

    estilo_header = ParagraphStyle(
        "CustomHeader",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=10,
        fontName="Helvetica-Bold",
    )
    estilo_secao = ParagraphStyle(
        "CustomSection",
        parent=styles["Heading2"],
        fontSize=16,
        textColor=colors.HexColor("#333333"),
        spaceBefore=15,
        spaceAfter=10,
        fontName="Helvetica-Bold",
    )
    estilo_normal = ParagraphStyle(
        "CustomNormal",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#333333"),
        fontName="Helvetica",
    )
    estilo_label = ParagraphStyle(
        "CustomLabel",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#333333"),
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    )
    estilo_valor = ParagraphStyle(
        "CustomValor",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#333333"),
        alignment=TA_CENTER,
        fontName="Helvetica",
    )

    elements = []

    # Cabeçalho
    header_data = [
        [Paragraph("Emissão de Passagem Aérea", estilo_header)],
        [
            Paragraph(
                f"Gerado em {(timezone.now() - timezone.timedelta(hours=3)).strftime('%d/%m/%Y às %H:%M')}",
                ParagraphStyle(
                    "HeaderSub",
                    parent=estilo_normal,
                    textColor=colors.white,
                    alignment=TA_CENTER,
                ),
            )
        ],
    ]
    header_table = Table(header_data, colWidths=[16 * cm], hAlign="CENTER")
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ff6b6b")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 15),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Informações do Cliente
    elements.append(Paragraph("Informações do Cliente", estilo_secao))

    cliente_data = [
        [
            Paragraph("NOME COMPLETO", estilo_label),
            Paragraph(
                emissao.cliente.usuario.get_full_name()
                or emissao.cliente.usuario.username,
                estilo_valor,
            ),
        ],
        [
            Paragraph("CPF", estilo_label),
            Paragraph(emissao.cliente.cpf or "-", estilo_valor),
        ],
    ]
    cliente_table = Table(cliente_data, colWidths=[7.5 * cm, 8 * cm], hAlign="CENTER")
    cliente_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(cliente_table)
    elements.append(Spacer(1, 20))

    # Dados da Emissão
    elements.append(Paragraph("Dados da Emissão", estilo_secao))

    dados_emissao = [
        [
            Paragraph("LOCALIZADOR", estilo_label),
            Paragraph(emissao.localizador or "-", estilo_valor),
        ],
        [
            Paragraph("COMPANHIA AÉREA", estilo_label),
            Paragraph(emissao.companhia_aerea or "-", estilo_valor),
        ],
        [
            Paragraph("DATA DE EMISSÃO", estilo_label),
            Paragraph(
                (timezone.now() - timezone.timedelta(hours=3)).strftime("%d/%m/%Y"),
                estilo_valor,
            ),
        ],
        [
            Paragraph("VALOR TOTAL", estilo_label),
            Paragraph(f"R$ {emissao.valor_pago:.2f}", estilo_valor),
        ],
    ]
    dados_emissao_table = Table(
        dados_emissao, colWidths=[7.5 * cm, 8 * cm], hAlign="CENTER"
    )
    dados_emissao_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(dados_emissao_table)
    elements.append(Spacer(1, 20))

    # Informações do Voo
    elements.append(Paragraph("Informações do Voo", estilo_secao))

    voo_data = [
        [
            Paragraph("ORIGEM", estilo_label),
            Paragraph(
                f"{emissao.aeroporto_partida.sigla} ({emissao.aeroporto_partida.nome})"
                if emissao.aeroporto_partida
                else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("DESTINO", estilo_label),
            Paragraph(
                f"{emissao.aeroporto_destino.sigla} ({emissao.aeroporto_destino.nome})"
                if emissao.aeroporto_destino
                else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("DATA IDA", estilo_label),
            Paragraph(
                emissao.data_ida.strftime("%d/%m/%Y") if emissao.data_ida else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("DATA VOLTA", estilo_label),
            Paragraph(
                emissao.data_volta.strftime("%d/%m/%Y")
                if emissao.data_volta
                else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("PROGRAMA DE FIDELIDADE", estilo_label),
            Paragraph(
                emissao.programa.nome if emissao.programa else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("PASSAGEIROS", estilo_label),
            Paragraph(str(emissao.qtd_passageiros), estilo_valor),
        ],
    ]
    voo_table = Table(voo_data, colWidths=[7.5 * cm, 8 * cm], hAlign="CENTER")
    voo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(voo_table)
    elements.append(Spacer(1, 20))

    # Rodapé
    footer_data = [
        [
            Paragraph(
                "Este documento confirma a emissão do bilhete. Guarde-o para referência.",
                ParagraphStyle(
                    "Footer1",
                    parent=estilo_normal,
                    textColor=colors.HexColor("#666666"),
                    alignment=TA_CENTER,
                    fontSize=10,
                ),
            )
        ],
        [
            Paragraph(
                f"Documento gerado automaticamente em {timezone.now().strftime('%d/%m/%Y')}",
                ParagraphStyle(
                    "Footer2",
                    parent=estilo_normal,
                    textColor=colors.HexColor("#666666"),
                    alignment=TA_CENTER,
                    fontSize=10,
                ),
            )
        ],
    ]
    footer_table = Table(footer_data, colWidths=[16 * cm], hAlign="CENTER")
    footer_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("TOPPADDING", (0, 0), (-1, -1), 15),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 15),
                ("LINEABOVE", (0, 0), (-1, 0), 1, colors.HexColor("#e9ecef")),
            ]
        )
    )
    elements.append(footer_table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf