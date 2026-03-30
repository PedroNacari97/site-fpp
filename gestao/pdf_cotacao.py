from io import BytesIO
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER

def gerar_pdf_cotacao(cotacao):
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
        'CustomHeader',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    estilo_secao = ParagraphStyle(
        'CustomSection',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#333333'),
        spaceBefore=15,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    estilo_normal = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        fontName='Helvetica'
    )
    estilo_label = ParagraphStyle(
        'CustomLabel',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    estilo_valor = ParagraphStyle(
        'CustomValor',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        fontName='Helvetica'
    )

    elements = []

    # Cabeçalho
    header_data = [
        [Paragraph("Cotação de Passagem Aérea", estilo_header)],
        [Paragraph(f"Gerado em {(timezone.now() - timezone.timedelta(hours=3)).strftime('%d/%m/%Y às %H:%M')}",
                  ParagraphStyle('HeaderSub', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER))]
    ]
    header_table = Table(header_data, colWidths=[16*cm], hAlign='CENTER')
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # Informações do Cliente
    elements.append(Paragraph("Informações do Cliente", estilo_secao))

    cliente_data = [
        [
            Paragraph("CLIENTE", estilo_label),
            Paragraph(cotacao.cliente.usuario.get_full_name() or cotacao.cliente.usuario.username, estilo_valor),
        ],
        [
            Paragraph("COMPANHIA AÉREA", estilo_label),
            Paragraph(cotacao.companhia_aerea or "-", estilo_valor),
        ],
        [
            Paragraph("PROGRAMA DE FIDELIDADE", estilo_label),
            Paragraph(cotacao.programa.nome if cotacao.programa else "-", estilo_valor),
        ],
        [
            Paragraph("PASSAGEIROS", estilo_label),
            Paragraph(f"{cotacao.qtd_passageiros} adultos", estilo_valor),
        ],
    ]

    cliente_table = Table(cliente_data, colWidths=[7.5*cm, 8*cm], hAlign='CENTER')
    cliente_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e9ecef')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(cliente_table)
    elements.append(Spacer(1, 20))

    # Rota do voo
    if cotacao.origem and cotacao.destino:
        rota_text = f"{cotacao.origem.sigla} ({cotacao.origem.nome}) ✈ {cotacao.destino.sigla} ({cotacao.destino.nome})"
        datas_text = f"Ida: {cotacao.data_ida.strftime('%d/%m/%Y às %H:%M')}"
        if cotacao.data_volta:
            datas_text += f" | Volta: {cotacao.data_volta.strftime('%d/%m/%Y às %H:%M')}"
        rota_data = [
            [Paragraph(rota_text, ParagraphStyle('RouteMain', parent=estilo_valor, fontSize=13, textColor=colors.white, alignment=TA_CENTER))],
            [Paragraph(datas_text, ParagraphStyle('RouteSub', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=12))]
        ]
        rota_table = Table(rota_data, colWidths=[16*cm], hAlign='CENTER')
        rota_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(rota_table)
        elements.append(Spacer(1, 20))

   # Comparativo de preços
    elements.append(Paragraph("Comparativo de Preços", estilo_secao))

    cotacao.calcular_valores()
    valor_referencia = cotacao.valor_passagem
    nossa_oferta = cotacao.valor_vista
    economia = valor_referencia - nossa_oferta
    perc_economia = (economia / valor_referencia) * 100 if valor_referencia else 0

    # Dados para as duas colunas: Valor de Referência e Nossa Oferta
    precos_data = [
        [
            Paragraph("VALOR DE REFERÊNCIA POR PESSOA", estilo_label),
            Paragraph("NOSSA OFERTA POR PESSOA", estilo_label),
            Paragraph("VALOR TOTAL", estilo_label),
        ],
        [
            Paragraph(f"R$ {valor_referencia:.2f}", ParagraphStyle('PrecoValor',  estilo_valor)),
            Paragraph(f"R$ {nossa_oferta:.2f}", ParagraphStyle('PrecoValor',  estilo_valor)),
            Paragraph(f"R$ {(cotacao.qtd_passageiros * nossa_oferta):.2f}", ParagraphStyle('PrecoValor',  estilo_valor)),
        ],

    ]

    precos_table = Table(precos_data, colWidths=[6*cm, 6*cm], hAlign='CENTER')
    precos_table.setStyle(TableStyle([
       ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
       ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
       ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
       ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e9ecef')),
       ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
       ('TOPPADDING', (0, 0), (-1, -1), 12),
       ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(precos_table)
    elements.append(Spacer(1, 20))

    # Destaque da economia
    economia_data = [
        [Paragraph("Você economiza com nossa oferta até:", ParagraphStyle('EconomiaText', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=14))],
        [Paragraph(f"R$ {economia:.2f}", ParagraphStyle('EconomiaValor', parent=estilo_valor, fontSize=28, textColor=colors.white, alignment=TA_CENTER))],
        [Paragraph("(POR PESSOA):", ParagraphStyle('Economiatext', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=10,))],
        [Paragraph(f"{perc_economia:.2f}% de desconto em relação ao valor de referência", ParagraphStyle('EconomiaDesc', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=11))]
    ]
    economia_table = Table(economia_data, colWidths=[16*cm], hAlign='CENTER')
    economia_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#28a745')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    elements.append(economia_table)
    elements.append(Spacer(1, 20))

    # Opções de Pagamento (totais apenas)
    elements.append(Paragraph("Opções de Pagamento", estilo_secao))
    valor_parcela = ((cotacao.valor_parcelado / cotacao.parcelas)*cotacao.qtd_passageiros) if cotacao.parcelas else cotacao.valor_parcelado * cotacao.qtd_passageiros
    valor_total_parcelado = valor_parcela * cotacao.parcelas if cotacao.parcelas else valor_parcela
    valor_total_vista = nossa_oferta * cotacao.qtd_passageiros
    desconto_valor = valor_total_parcelado - valor_total_vista

    pagamento_data = [
    
        [Paragraph(f"<b>Pagamento Parcelado</b>", estilo_label), Paragraph(f"Em até ({cotacao.parcelas}x de R$ {valor_parcela:.2f}) = R$ {valor_total_parcelado:.2f}", estilo_valor)],
        [Paragraph(f"<b>Pagamento à Vista</b>", estilo_label), Paragraph(f"R$ {valor_total_vista:.2f} (Desconto de R$ {desconto_valor:.2f})", estilo_valor)]
    ]

    pagamento_table = Table(pagamento_data, colWidths=[8*cm, 8*cm], hAlign='CENTER')
    pagamento_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e9ecef')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
    ]))
    elements.append(pagamento_table)
    elements.append(Spacer(1, 20))

    # Validade
    if cotacao.validade:
        validade_data = [
            [Paragraph(f"⏰ Esta cotação é válida até {cotacao.validade.strftime('%d/%m/%Y')}",
                      ParagraphStyle('Validade', parent=estilo_valor, textColor=colors.HexColor('#856404'), alignment=TA_CENTER, fontSize=12))]
        ]
        validade_table = Table(validade_data, colWidths=[16*cm], hAlign='CENTER')
        validade_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff3cd')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#ffeaa7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        elements.append(validade_table)
        elements.append(Spacer(1, 20))

    # Rodapé
    footer_data = [
        [Paragraph("Esta é uma proposta de cotação. Valores sujeitos à disponibilidade.",
                  ParagraphStyle('Footer1', parent=estilo_normal, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, fontSize=10))],
        [Paragraph(f"Documento gerado automaticamente em {timezone.now().strftime('%d/%m/%Y')}",
                  ParagraphStyle('Footer2', parent=estilo_normal, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, fontSize=10))]
    ]
    footer_table = Table(footer_data, colWidths=[16*cm], hAlign='CENTER')
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#e9ecef')),
    ]))
    elements.append(footer_table)

    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf