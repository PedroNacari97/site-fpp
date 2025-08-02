from io import BytesIO
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
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
    """
    Gera PDF da emissão seguindo o layout do PDF de cotação, com informações e valores formatados.
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

    # Estilos baseados no PDF de cotação
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
        textColor=colors.HexColor("#666666"),
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )
    estilo_valor = ParagraphStyle(
        "CustomValor",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.HexColor("#000000"),
        fontName="Helvetica-Bold",
        alignment=TA_LEFT,
    )
    estilo_valor_destaque = ParagraphStyle(
        "CustomValorDestaque",
        parent=styles["Normal"],
        fontSize=14,
        textColor=colors.HexColor("#28a745"),  # Verde destaque
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )

    elements = []

    # Cabeçalho colorido
    header_data = [
        [Paragraph("Confirmação de Emissão de Passagem", estilo_header)],
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
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#667eea")),  # Azul semelhante à cotação
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Informações do Cliente - 2 colunas lado a lado, centralizadas
    elements.append(Paragraph("Informações do Cliente", estilo_secao))
    cliente_data = [
        [
            Paragraph("Nome Completo:", estilo_label),
            Paragraph(
                emissao.cliente.usuario.get_full_name() or emissao.cliente.usuario.username,
                estilo_valor,
            ),
        ],
        [
            Paragraph("CPF:", estilo_label),
            Paragraph(emissao.cliente.cpf or "-", estilo_valor),
        ],
    ]
    cliente_table = Table(cliente_data, colWidths=[6 * cm, 10 * cm], hAlign="CENTER")
    cliente_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(cliente_table)
    elements.append(Spacer(1, 20))

    # Dados da Emissão com valores formatados e estilo parecido com cotação
    elements.append(Paragraph("Dados da Emissão", estilo_secao))
    dados_emissao = [
        [
            Paragraph("Localizador:", estilo_label),
            Paragraph(emissao.localizador or "-", estilo_valor),
        ],
        [
            Paragraph("Companhia Aérea:", estilo_label),
            Paragraph(emissao.companhia_aerea or "-", estilo_valor),
        ],
        [
            Paragraph("Data de Emissão:", estilo_label),
            Paragraph(
                emissao.data_ida.strftime("%d/%m/%Y") if emissao.data_ida else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Valor Total Pago:", estilo_label),
            Paragraph(f"R$ {emissao.valor_pago:.2f}", estilo_valor_destaque),
        ],
    ]
    dados_table = Table(dados_emissao, colWidths=[6 * cm, 10 * cm], hAlign="CENTER")
    dados_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(dados_table)
    elements.append(Spacer(1, 20))

    # Informações do Voo (origem, destino, datas, programa, passageiros)
    elements.append(Paragraph("Informações do Voo", estilo_secao))
    voo_data = [
        [
            Paragraph("Origem:", estilo_label),
            Paragraph(
                f"{emissao.aeroporto_partida.sigla} - {emissao.aeroporto_partida.nome}"
                if emissao.aeroporto_partida else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Destino:", estilo_label),
            Paragraph(
                f"{emissao.aeroporto_destino.sigla} - {emissao.aeroporto_destino.nome}"
                if emissao.aeroporto_destino else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Data Ida:", estilo_label),
            Paragraph(
                emissao.data_ida.strftime("%d/%m/%Y") if emissao.data_ida else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Data Volta:", estilo_label),
            Paragraph(
                emissao.data_volta.strftime("%d/%m/%Y") if emissao.data_volta else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Programa de Fidelidade:", estilo_label),
            Paragraph(
                emissao.programa.nome if emissao.programa else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Passageiros:", estilo_label),
            Paragraph(str(emissao.qtd_passageiros), estilo_valor),
        ],
    ]
    voo_table = Table(voo_data, colWidths=[6 * cm, 10 * cm], hAlign="CENTER")
    voo_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
            ]
        )
    )
    elements.append(voo_table)
    elements.append(Spacer(1, 20))

    # Rodapé padrão
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
