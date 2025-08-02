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
        textColor=colors.HexColor("#28a745"),
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    estilo_link = ParagraphStyle(
        "CustomLink",
        parent=estilo_valor,
        textColor=colors.HexColor("#3366cc"),
        underline=True,
        alignment=TA_LEFT,
    )

    companhia = emissao.companhia_aerea
    if companhia:
        companhia_nome = getattr(companhia, "nome", str(companhia))
        companhia_link = getattr(companhia, "site_url", None)
    else:
        companhia_nome = "-"
        companhia_link = None

    if companhia_link:
        companhia_para_pdf = Paragraph(
            f'<link href="{companhia_link}">{companhia_nome}</link>',
            estilo_link,
        )
    else:
        companhia_para_pdf = Paragraph(companhia_nome, estilo_valor)

    localizador_para_pdf = Paragraph(emissao.localizador or "-", estilo_valor)

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
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#667eea")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 18),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    elements.append(header_table)
    info_left = [[Paragraph("Companhia Aérea:", estilo_label), companhia_para_pdf]]
    info_right = [[Paragraph("Localizador:", estilo_label), localizador_para_pdf]]
    info_table = Table(
        [
            [
                Table(info_left, colWidths=[4 * cm, 4 * cm]),
                Table(info_right, colWidths=[3.5 * cm, 4.5 * cm]),
            ]
        ],
        colWidths=[8 * cm, 8 * cm],
        hAlign="CENTER",
    )
    info_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8f9fa")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e9ecef")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(info_table)
    elements.append(Spacer(1, 12))

    # Informações do Cliente
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

    # Dados da Emissão
    elements.append(Paragraph("Dados da Emissão", estilo_secao))

    dados_emissao = [
        [
            Paragraph("Companhia Aérea:", estilo_label),
            companhia_para_pdf,
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
        [
            Paragraph("Valor de Referência:", estilo_label),
            Paragraph(
                f"R$ {getattr(emissao, 'valor_referencia', 0):.2f}" if getattr(emissao, 'valor_referencia', None) else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("Valor Economizado:", estilo_label),
            Paragraph(
                f"R$ {getattr(emissao, 'valor_economizado', 0):.2f}" if getattr(emissao, 'valor_economizado', None) else "-",
                estilo_valor,
            ),
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
    ]
    voo_data.append(
        [
            Paragraph("Passageiros:", estilo_label),
            Paragraph(
                f"Adultos: {emissao.qtd_adultos}  Crianças: {emissao.qtd_criancas}  Bebês: {emissao.qtd_bebes}",
                estilo_valor,
            ),
        ]
    )
    if getattr(emissao, "possui_escala", False):
        voo_data.append(
            [
                Paragraph("Aeroporto de escala:", estilo_label),
                Paragraph(
                    f"{emissao.aeroporto_escala.sigla} - {emissao.aeroporto_escala.nome}"
                    if emissao.aeroporto_escala
                    else "-",
                    estilo_valor,
                ),
            ]
        )
        voo_data.append(
            [
                Paragraph("Duração da escala:", estilo_label),
                Paragraph(
                    str(emissao.duracao_escala) if emissao.duracao_escala else "-",
                    estilo_valor,
                ),
            ]
        )
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

    # Passageiros detalhados por categoria
    elements.append(Paragraph("Passageiros", estilo_secao))
    categorias = [
        ("adulto", "Adultos"),
        ("crianca", "Crianças"),
        ("bebe", "Bebês"),
    ]
    for chave, titulo in categorias:
        passageiros = emissao.passageiros.filter(categoria=chave)
        if passageiros.exists():
            dados = [[Paragraph("Nome", estilo_label), Paragraph("Documento", estilo_label)]]
            for p in passageiros:
                dados.append(
                    [Paragraph(p.nome, estilo_valor), Paragraph(p.documento, estilo_valor)]
                )
            tabela = Table(dados, colWidths=[8 * cm, 8 * cm], hAlign="CENTER")
            tabela.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e9ecef")),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                        ("TOPPADDING", (0, 0), (-1, -1), 8),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                    ]
                )
            )
            elements.append(Paragraph(titulo, estilo_label))
            elements.append(tabela)
            elements.append(Spacer(1, 10))

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
