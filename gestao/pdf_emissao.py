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
    Gera PDF da emissão seguindo o layout melhorado,
    com todas as seções ajustadas.
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

    # Estilos customizados
    estilo_header = ParagraphStyle(
        "CustomHeader",
        parent=styles["Title"],
        fontSize=24,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=10,
        fontName="Helvetica-Bold",
    )
    estilo_localizador = ParagraphStyle(
        "LocalizadorDestaque",
        parent=styles["Normal"],
        fontSize=18,
        textColor=colors.HexColor("#2563eb"),
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
        spaceBefore=6,
        spaceAfter=14,
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

    # 1. Cabeçalho colorido
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
                ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
                ("LEFTPADDING", (0, 0), (-1, -1), 20),
                ("RIGHTPADDING", (0, 0), (-1, -1), 20),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 16))

    # 2. Localizador em destaque
    elements.append(Paragraph("LOCALIZADOR", estilo_label))
    elements.append(Paragraph(emissao.localizador or "-", estilo_localizador))
    elements.append(Spacer(1, 8))

    # 3. Informações do Cliente
    elements.append(Paragraph("Informações do Cliente", estilo_secao))
    cliente_data = [
        [
            Paragraph("NOME COMPLETO", estilo_label),
            Paragraph(
                emissao.cliente.usuario.get_full_name() or emissao.cliente.usuario.username,
                estilo_valor,
            ),
        ],
        [
            Paragraph("CPF", estilo_label),
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
    elements.append(Spacer(1, 14))

    # 4. Dados da Emissão (agora com menos campos)
    elements.append(Paragraph("Dados da Emissão", estilo_secao))
    dados_emissao = [
        [
            Paragraph("COMPANHIA AÉREA", estilo_label),
            Paragraph(emissao.companhia_aerea or "-", estilo_valor),
        ],
        [
            Paragraph("DATA DE EMISSÃO", estilo_label),
            Paragraph(
                emissao.data_ida.strftime("%d/%m/%Y") if emissao.data_ida else "-",
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
    elements.append(Spacer(1, 14))

    # 5. Informações Financeiras
    elements.append(Paragraph("Informações Financeiras", estilo_secao))
    valor_referencia = getattr(emissao, "valor_referencia", None) or 0
    valor_pago = emissao.valor_pago or 0
    valor_economizado = (valor_referencia - valor_pago) if valor_referencia else 0
    percentual_economia = (
        (valor_economizado / valor_referencia * 100) if valor_referencia else 0
    )

    financeiras_data = [
        [
            Paragraph("VALOR DE REFERÊNCIA", estilo_label),
            Paragraph(f"R$ {valor_referencia:,.2f}", estilo_valor),
        ],
        [
            Paragraph("VALOR TOTAL PAGO", estilo_label),
            Paragraph(f"R$ {valor_pago:,.2f}", estilo_valor),
        ],
        [
            Paragraph("VALOR ECONOMIZADO", estilo_label),
            Paragraph(f"R$ {valor_economizado:,.2f}", estilo_valor_destaque),
        ],
        [
            Paragraph("PERCENTUAL DE ECONOMIA", estilo_label),
            Paragraph(f"{percentual_economia:.2f}%", estilo_valor),
        ],
    ]
    financeiras_table = Table(financeiras_data, colWidths=[6 * cm, 10 * cm], hAlign="CENTER")
    financeiras_table.setStyle(
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
    elements.append(financeiras_table)
    elements.append(Spacer(1, 14))

    # 6. Informações do Voo
    elements.append(Paragraph("Informações do Voo", estilo_secao))
    voo_data = [
        [
            Paragraph("ORIGEM", estilo_label),
            Paragraph(
                f"{emissao.aeroporto_partida.sigla} - {emissao.aeroporto_partida.nome}"
                if emissao.aeroporto_partida else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("DESTINO", estilo_label),
            Paragraph(
                f"{emissao.aeroporto_destino.sigla} - {emissao.aeroporto_destino.nome}"
                if emissao.aeroporto_destino else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("DATA DE IDA", estilo_label),
            Paragraph(
                emissao.data_ida.strftime("%d/%m/%Y") if emissao.data_ida else "-",
                estilo_valor,
            ),
        ],
        [
            Paragraph("DATA DE VOLTA", estilo_label),
            Paragraph(
                emissao.data_volta.strftime("%d/%m/%Y") if emissao.data_volta else "-",
                estilo_valor,
            ),
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
    elements.append(Spacer(1, 14))

    # 7. Escalas (se houver)
    escalas = emissao.escalas.all()
    if escalas.exists():
        elements.append(Paragraph("Escalas", estilo_secao))
        dados_escalas = [[
            Paragraph("Aeroporto", estilo_label),
            Paragraph("Duração", estilo_label),
            Paragraph("Cidade/País", estilo_label),
        ]]
        for e in escalas:
            total_seconds = int(e.duracao.total_seconds())
            h = total_seconds // 3600
            m = (total_seconds % 3600) // 60
            dados_escalas.append([
                Paragraph(f"{e.aeroporto.sigla} - {e.aeroporto.nome}", estilo_valor),
                Paragraph(f"{h:02d}:{m:02d}", estilo_valor),
                Paragraph(e.cidade or "-", estilo_valor),
            ])
        tabela_escalas = Table(dados_escalas, colWidths=[5 * cm, 4 * cm, 7 * cm], hAlign="CENTER")
        tabela_escalas.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8f9fa")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e9ecef")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(tabela_escalas)
        elements.append(Spacer(1, 14))

    # 8. Passageiros (total e listas)
    elements.append(Paragraph("Passageiros", estilo_secao))

    qtd_adultos = getattr(emissao, "qtd_adultos", 0)
    qtd_criancas = getattr(emissao, "qtd_criancas", 0)
    qtd_bebes = getattr(emissao, "qtd_bebes", 0)

    # Resumo total de passageiros
    resumo_passageiros = f"TOTAL DE PASSAGEIROS: Adultos: {qtd_adultos} | Crianças: {qtd_criancas} | Bebês: {qtd_bebes}"
    elements.append(Paragraph(resumo_passageiros, estilo_label))
    elements.append(Spacer(1, 5))

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

    # 9. Rodapé padrão
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
