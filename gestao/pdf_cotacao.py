from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from gestao.services.cotacao_preview import build_cotacao_preview_context


PAGE_WIDTH = 18.2 * cm


def _build_styles():
    styles = getSampleStyleSheet()
    return {
        "brand_title": ParagraphStyle(
            "BrandTitle",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=22,
            textColor=colors.white,
            spaceAfter=2,
        ),
        "brand_subtitle": ParagraphStyle(
            "BrandSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=11,
            textColor=colors.HexColor("#E0E7FF"),
        ),
        "badge_label": ParagraphStyle(
            "BadgeLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#E9D5FF"),
            textTransform="uppercase",
        ),
        "badge_value": ParagraphStyle(
            "BadgeValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=18,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#94A3B8"),
            textTransform="uppercase",
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
        ),
        "section_title": ParagraphStyle(
            "SectionTitle",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=14,
            textColor=colors.HexColor("#0F172A"),
        ),
        "card_label": ParagraphStyle(
            "CardLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#94A3B8"),
            textTransform="uppercase",
        ),
        "card_value": ParagraphStyle(
            "CardValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
        ),
        "route_city": ParagraphStyle(
            "RouteCity",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            textColor=colors.HexColor("#0F172A"),
        ),
        "route_hint": ParagraphStyle(
            "RouteHint",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#64748B"),
        ),
        "route_center": ParagraphStyle(
            "RouteCenter",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#7C3AED"),
        ),
        "value_row_label": ParagraphStyle(
            "ValueRowLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#0F172A"),
        ),
        "value_row_hint": ParagraphStyle(
            "ValueRowHint",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#94A3B8"),
        ),
        "value_row_amount": ParagraphStyle(
            "ValueRowAmount",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=13,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#0F172A"),
        ),
        "highlight_label": ParagraphStyle(
            "HighlightLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=12,
            textColor=colors.HexColor("#0F172A"),
        ),
        "highlight_hint": ParagraphStyle(
            "HighlightHint",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.5,
            leading=9,
            textColor=colors.HexColor("#64748B"),
        ),
        "highlight_value_green": ParagraphStyle(
            "HighlightValueGreen",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=21,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#16A34A"),
        ),
        "highlight_value_blue": ParagraphStyle(
            "HighlightValueBlue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=19,
            leading=21,
            alignment=TA_RIGHT,
            textColor=colors.HexColor("#2563EB"),
        ),
        "alert_text": ParagraphStyle(
            "AlertText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#7C2D12"),
        ),
        "condition_text": ParagraphStyle(
            "ConditionText",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            textColor=colors.HexColor("#334155"),
        ),
        "footer_label": ParagraphStyle(
            "FooterLabel",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.5,
            leading=9,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#94A3B8"),
            textTransform="uppercase",
        ),
        "footer_value": ParagraphStyle(
            "FooterValue",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
            textColor=colors.white,
        ),
    }


def _card_content(label, value, styles):
    return [
        Paragraph(label, styles["card_label"]),
        Spacer(1, 0.15 * cm),
        Paragraph(value, styles["card_value"]),
    ]


def _info_grid(items, columns, styles):
    rows = []
    row = []
    col_width = PAGE_WIDTH / columns
    for item in items:
        row.append(_card_content(item["label"], item["value"], styles))
        if len(row) == columns:
            rows.append(row)
            row = []
    if row:
        while len(row) < columns:
            row.append("")
        rows.append(row)

    table = Table(rows, colWidths=[col_width] * columns, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FAFC")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def _section_heading(title, tone_color, styles):
    icon = Table(
        [[Paragraph("o", ParagraphStyle("IconDot", parent=styles["section_title"], textColor=tone_color, alignment=TA_CENTER))]],
        colWidths=[0.55 * cm],
        rowHeights=[0.55 * cm],
    )
    icon.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.8, tone_color),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    heading = Table(
        [[icon, Paragraph(title, styles["section_title"])]],
        colWidths=[0.75 * cm, PAGE_WIDTH - 0.75 * cm],
        hAlign="LEFT",
    )
    heading.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return heading


def _hero_table(context, styles):
    brand = Table(
        [[
            Table(
                [[Paragraph("N", ParagraphStyle("MarkIcon", parent=styles["brand_title"], fontSize=15, alignment=TA_CENTER, textColor=colors.HexColor("#2563EB")))]],
                colWidths=[0.9 * cm],
                rowHeights=[0.9 * cm],
            ),
            [Paragraph("NC Fly", styles["brand_title"]), Paragraph("Consultoria em Milhas e Viagens", styles["brand_subtitle"])],
        ]],
        colWidths=[1.1 * cm, 10.7 * cm],
    )
    brand.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#FFFFFF")),
                ("TEXTCOLOR", (0, 0), (0, 0), colors.HexColor("#2563EB")),
                ("ALIGN", (0, 0), (0, 0), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )

    badge = Table(
        [
            [Paragraph("COTACAO No", styles["badge_label"])],
            [Paragraph(context["cotacao_numero"], styles["badge_value"])],
        ],
        colWidths=[3.1 * cm],
    )
    badge.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#9333EA")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )

    hero = Table([[brand, badge]], colWidths=[12.7 * cm, 4.5 * cm], hAlign="LEFT")
    hero.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#5B3DF5")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 14),
                ("RIGHTPADDING", (0, 0), (-1, -1), 14),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
            ]
        )
    )
    return hero


def _meta_table(cotacao, styles):
    data = [
        _card_content("Data de emissao", cotacao.criado_em.strftime("%d/%m/%Y"), styles),
        _card_content("Validade", cotacao.validade.strftime("%d/%m/%Y") if cotacao.validade else "A confirmar", styles),
    ]
    table = Table([data], colWidths=[PAGE_WIDTH / 2, PAGE_WIDTH / 2], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _route_table(cotacao, context, styles):
    route = Table(
        [[
            [
                Paragraph("ORIGEM", styles["card_label"]),
                Spacer(1, 0.12 * cm),
                Paragraph(context["origem_nome"], styles["route_city"]),
                Spacer(1, 0.08 * cm),
                Paragraph(cotacao.data_ida.strftime("%d/%m/%Y"), styles["route_hint"]),
            ],
            [
                Paragraph(f'{context["origem_sigla"]}  ->  {context["destino_sigla"]}', styles["route_center"]),
            ],
            [
                Paragraph("DESTINO", ParagraphStyle("RouteDest", parent=styles["card_label"], alignment=TA_RIGHT)),
                Spacer(1, 0.12 * cm),
                Paragraph(context["destino_nome"], ParagraphStyle("RouteDestCity", parent=styles["route_city"], alignment=TA_RIGHT)),
                Spacer(1, 0.08 * cm),
                Paragraph(
                    cotacao.data_volta.strftime("%d/%m/%Y") if cotacao.data_volta else "Somente ida",
                    ParagraphStyle("RouteDestHint", parent=styles["route_hint"], alignment=TA_RIGHT),
                ),
            ],
        ]],
        colWidths=[6.4 * cm, 4.2 * cm, 7.6 * cm],
        hAlign="LEFT",
    )
    route.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FAF7FF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#EDE9FE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return route


def _value_rows(context, styles):
    rows = []
    for item in context["valor_items"]:
        rows.append(
            [
                [Paragraph(item["label"], styles["value_row_label"]), Paragraph(item["hint"], styles["value_row_hint"])],
                Paragraph(item["value"], styles["value_row_amount"]),
            ]
        )
    table = Table(rows, colWidths=[12.5 * cm, 5.7 * cm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FBFDFF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#E2E8F0")),
                ("INNERGRID", (0, 0), (-1, -1), 0.8, colors.HexColor("#E2E8F0")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _highlight_card(label, hint, value, border_color, fill_color, value_style, styles):
    table = Table(
        [[
            [Paragraph(label, styles["highlight_label"]), Paragraph(hint, styles["highlight_hint"])],
            Paragraph(value, value_style),
        ]],
        colWidths=[10.4 * cm, 7.8 * cm],
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), fill_color),
                ("BOX", (0, 0), (-1, -1), 1, border_color),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def _conditions_table(items, styles):
    paragraphs = []
    for item in items:
        paragraphs.append(Paragraph(f"- {item}", styles["condition_text"]))
        paragraphs.append(Spacer(1, 0.08 * cm))
    table = Table([[paragraphs]], colWidths=[PAGE_WIDTH], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8FBFF")),
                ("BOX", (0, 0), (-1, -1), 0.8, colors.HexColor("#DBEAFE")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    return table


def _contact_table(company_contact, styles):
    data = [[
        [Paragraph("Telefone", styles["footer_label"]), Paragraph(company_contact["telefone"], styles["footer_value"])],
        [Paragraph("E-mail", styles["footer_label"]), Paragraph(company_contact["email"], styles["footer_value"])],
        [Paragraph("Website", styles["footer_label"]), Paragraph(company_contact["website"], styles["footer_value"])],
    ]]
    table = Table(data, colWidths=[PAGE_WIDTH / 3] * 3, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#111827")),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 12),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    return table


def gerar_pdf_cotacao(cotacao):
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.25 * cm,
        rightMargin=1.25 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = _build_styles()
    context = build_cotacao_preview_context(cotacao)
    elements = []

    elements.append(_hero_table(context, styles))
    elements.append(_meta_table(cotacao, styles))
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(_section_heading("Dados do Cliente", colors.HexColor("#2563EB"), styles))
    elements.append(Spacer(1, 0.18 * cm))
    elements.append(
        _info_grid(
            [
                {"label": "Nome completo", "value": context["titular_info"]["nome"]},
                {"label": "CPF", "value": context["titular_info"]["cpf"]},
                {"label": "E-mail", "value": context["titular_info"]["email"]},
                {"label": "Telefone", "value": context["titular_info"]["telefone"]},
            ],
            2,
            styles,
        )
    )
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(_section_heading("Detalhes do Voo", colors.HexColor("#9333EA"), styles))
    elements.append(Spacer(1, 0.18 * cm))
    elements.append(_route_table(cotacao, context, styles))
    elements.append(Spacer(1, 0.16 * cm))
    elements.append(
        _info_grid(
            [
                {"label": "Classe", "value": context["classe_label"]},
                {"label": "Companhia", "value": context["companhia_label"]},
                {"label": "Passageiros", "value": context["qtd_passageiros_label"]},
                {"label": "Programa", "value": context["programa_label"]},
            ],
            4,
            styles,
        )
    )
    optional_cards = []
    if context["tem_volta"]:
        optional_cards.append(
            {
                "label": "Horario da volta",
                "value": cotacao.data_volta.strftime("%d/%m/%Y %H:%M"),
            }
        )
    if context["escalas_ida"]:
        optional_cards.append(
            {
                "label": "Escalas na ida",
                "value": " / ".join(escala.aeroporto.sigla for escala in context["escalas_ida"]),
            }
        )
    if context["escalas_volta"]:
        optional_cards.append(
            {
                "label": "Escalas na volta",
                "value": " / ".join(escala.aeroporto.sigla for escala in context["escalas_volta"]),
            }
        )
    if optional_cards:
        elements.append(Spacer(1, 0.14 * cm))
        elements.append(_info_grid(optional_cards, 3 if len(optional_cards) > 1 else 1, styles))
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(_section_heading("Valores", colors.HexColor("#16A34A"), styles))
    elements.append(Spacer(1, 0.18 * cm))
    elements.append(_value_rows(context, styles))
    elements.append(Spacer(1, 0.16 * cm))
    elements.append(
        _highlight_card(
            "Valor a Vista",
            "Pagamento integral",
            context["valor_vista_total"],
            colors.HexColor("#4ADE80"),
            colors.HexColor("#ECFDF5"),
            styles["highlight_value_green"],
            styles,
        )
    )
    elements.append(Spacer(1, 0.12 * cm))
    elements.append(
        _highlight_card(
            "Valor Parcelado",
            context["valor_parcelado_hint"],
            context["valor_parcelado_total"],
            colors.HexColor("#60A5FA"),
            colors.HexColor("#EFF6FF"),
            styles["highlight_value_blue"],
            styles,
        )
    )
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(_section_heading("Observacoes Importantes", colors.HexColor("#F97316"), styles))
    elements.append(Spacer(1, 0.18 * cm))
    alert_table = Table([[Paragraph(context["observacao_importante"], styles["alert_text"])]], colWidths=[PAGE_WIDTH], hAlign="LEFT")
    alert_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#FFF7ED")),
                ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor("#F97316")),
                ("LEFTPADDING", (0, 0), (-1, -1), 12),
                ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(alert_table)
    elements.append(Spacer(1, 0.35 * cm))

    elements.append(Paragraph("Condicoes Gerais", styles["section_title"]))
    elements.append(Spacer(1, 0.18 * cm))
    elements.append(_conditions_table(context["condicoes_gerais"], styles))
    elements.append(Spacer(1, 0.42 * cm))
    elements.append(_contact_table(context["empresa_contato"], styles))

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
