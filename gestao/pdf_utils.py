from io import BytesIO
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def gerar_pdf_cotacao(cotacao):
    """Gera um PDF detalhado com layout moderno para uma CotacaoVoo."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=1.5 * cm,
        bottomMargin=2 * cm,
    )
    
    # Estilos personalizados
    styles = getSampleStyleSheet()
    
    # Estilo para o cabeçalho
    estilo_header = ParagraphStyle(
        'CustomHeader',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=10,
        fontName='Helvetica-Bold'
    )
    
    # Estilo para subtítulos
    estilo_secao = ParagraphStyle(
        'CustomSection',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#333333'),
        spaceBefore=15,
        spaceAfter=10,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=colors.HexColor('#667eea'),
        borderPadding=5
    )
    
    # Estilo para texto normal
    estilo_normal = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        fontName='Helvetica'
    )
    
    # Estilo para destaque
    estilo_destaque = ParagraphStyle(
        'CustomDestaque',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.white,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )

    elements = []

    # === CABEÇALHO COM FUNDO COLORIDO ===
    # Criando uma tabela para simular o fundo colorido
    header_data = [
        [Paragraph("Cotação de Passagem Aérea", estilo_header)],
        [Paragraph(f"Gerado em {timezone.now().strftime('%d/%m/%Y às %H:%M')}", 
                  ParagraphStyle('HeaderSub', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER))]
    ]
    
    header_table = Table(header_data, colWidths=[16*cm])
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

    # === INFORMAÇÕES DO CLIENTE ===
    elements.append(Paragraph("Informações do Cliente", estilo_secao))
    
    cliente_data = [
        ["Cliente", cotacao.cliente.usuario.get_full_name() or cotacao.cliente.usuario.username],
        ["Companhia Aérea", cotacao.companhia_aerea or "-"],
        ["Programa de Fidelidade", cotacao.programa.nome if cotacao.programa else "-"],
        ["Passageiros", f"{cotacao.qtd_passageiros} adultos"]
    ]
    
    # Criando grid 2x2 para informações do cliente
    cliente_grid = []
    for i in range(0, len(cliente_data), 2):
        row = []
        for j in range(2):
            if i + j < len(cliente_data):
                label, value = cliente_data[i + j]
                cell_content = f"<font size=9 color='#666666'>{label.upper()}</font><br/><font size=11 color='#333333'><b>{value}</b></font>"
                row.append(Paragraph(cell_content, estilo_normal))
            else:
                row.append("")
        cliente_grid.append(row)
    
    cliente_table = Table(cliente_grid, colWidths=[8*cm, 8*cm])
    cliente_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(cliente_table)
    elements.append(Spacer(1, 20))

    # === ROTA DO VOO ===
    if cotacao.origem and cotacao.destino:
        rota_text = f"{cotacao.origem.cidade} ({cotacao.origem.sigla}) ✈ {cotacao.destino.cidade} ({cotacao.destino.sigla})"
        datas_text = f"Ida: {cotacao.data_ida.strftime('%d/%m/%Y às %H:%M')}"
        if cotacao.data_volta:
            datas_text += f" | Volta: {cotacao.data_volta.strftime('%d/%m/%Y às %H:%M')}"
        
        rota_data = [
            [Paragraph(rota_text, ParagraphStyle('RouteMain', parent=estilo_destaque, fontSize=18))],
            [Paragraph(datas_text, ParagraphStyle('RouteSub', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=12))]
        ]
        
        rota_table = Table(rota_data, colWidths=[16*cm])
        rota_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#667eea')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        
        elements.append(rota_table)
        elements.append(Spacer(1, 20))

    # === COMPARATIVO DE PREÇOS ===
    elements.append(Paragraph("Comparativo de Preços", estilo_secao))
    
    # Calculando valores
    cotacao.calcular_valores()
    valor_referencia = cotacao.valor_passagem
    valor_empresa = cotacao.valor_passagem  # Assumindo que é o mesmo
    nossa_oferta = cotacao.valor_vista
    economia = valor_referencia - nossa_oferta
    perc_economia = (economia / valor_referencia) * 100 if valor_referencia else 0
    
    # Grid de preços 3 colunas
    precos_data = [
        [
            f"<font size=9 color='#666666'>VALOR DE REFERÊNCIA</font><br/><font size=20 color='#333333'><b>R$ {valor_referencia:.2f}</b></font><br/><font size=9 color='#666666'>Preço médio no mercado</font>",
            f"<font size=9 color='#666666'>NOSSA OFERTA</font><br/><font size=20 color='#333333'><b>R$ {nossa_oferta:.2f}</b></font><br/><font size=9 color='#666666'>Com milhas + taxas</font>",
            f"<font size=9 color='#666666'>VALOR NA EMPRESA</font><br/><font size=20 color='#333333'><b>R$ {valor_empresa:.2f}</b></font><br/><font size=9 color='#666666'>Preço direto da cia.</font>"
        ]
    ]
    
    precos_table = Table(precos_data, colWidths=[5.3*cm, 5.3*cm, 5.3*cm])
    precos_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), colors.white),
        ('BACKGROUND', (1, 0), (1, 0), colors.white),
        ('BACKGROUND', (2, 0), (2, 0), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('BOX', (1, 0), (1, 0), 2, colors.HexColor('#28a745')),  # Destaque na nossa oferta
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e9ecef')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    
    elements.append(precos_table)
    elements.append(Spacer(1, 15))

    # === DESTAQUE DA ECONOMIA ===
    economia_data = [
        [Paragraph("Você economiza com nossa oferta:", ParagraphStyle('EconomiaText', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=14))],
        [Paragraph(f"R$ {economia:.2f}", ParagraphStyle('EconomiaValor', parent=estilo_destaque, fontSize=28))],
        [Paragraph(f"{perc_economia:.0f}% de desconto em relação ao valor de referência", ParagraphStyle('EconomiaDesc', parent=estilo_normal, textColor=colors.white, alignment=TA_CENTER, fontSize=11))]
    ]
    
    economia_table = Table(economia_data, colWidths=[16*cm])
    economia_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#28a745')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    elements.append(economia_table)
    elements.append(Spacer(1, 20))

    # === DETALHES DA COTAÇÃO ===
    elements.append(Paragraph("Detalhes da Cotação", estilo_secao))
    
    detalhes_data = [
        ["Milhas Necessárias", f"{cotacao.milhas:,}".replace(",", ".") + " milhas"],
        ["Valor do Milheiro", f"R$ {cotacao.valor_milheiro:.2f}"],
        ["Taxas e Impostos", f"R$ {cotacao.taxas:.2f}"],
        ["Classe", cotacao.classe or "Econômica"]
    ]
    
    # Grid 2x2 para detalhes
    detalhes_grid = []
    for i in range(0, len(detalhes_data), 2):
        row = []
        for j in range(2):
            if i + j < len(detalhes_data):
                label, value = detalhes_data[i + j]
                cell_content = f"<font size=9 color='#666666'>{label.upper()}</font><br/><font size=11 color='#333333'><b>{value}</b></font>"
                row.append(Paragraph(cell_content, estilo_normal))
            else:
                row.append("")
        detalhes_grid.append(row)
    
    detalhes_table = Table(detalhes_grid, colWidths=[8*cm, 8*cm])
    detalhes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    elements.append(detalhes_table)
    elements.append(Spacer(1, 20))

    # === OPÇÕES DE PAGAMENTO ===
    elements.append(Paragraph("Opções de Pagamento", estilo_secao))
    
    # Calculando valores de pagamento
    valor_parcela = cotacao.valor_parcelado / cotacao.parcelas if cotacao.parcelas else cotacao.valor_parcelado
    juros_valor = cotacao.valor_parcelado - cotacao.valor_vista
    desconto_valor = cotacao.valor_parcelado - cotacao.valor_vista
    
    pagamento_data = [
        [
            f"<font size=12 color='#333333'><b>💳 Pagamento Parcelado</b></font><br/><br/>"
            f"<font size=10 color='#666666'>Valor base:</font> <font size=10 color='#333333'>R$ {cotacao.valor_vista:.2f}</font><br/>"
            f"<font size=10 color='#666666'>Juros ({cotacao.juros:.1f}%):</font> <font size=10 color='#333333'>R$ {juros_valor:.2f}</font><br/><br/>"
            f"<font size=12 color='#333333'><b>{cotacao.parcelas}x de R$ {valor_parcela:.2f}</b></font> <font size=12 color='#333333'><b>R$ {cotacao.valor_parcelado:.2f}</b></font>",
            
            f"<font size=12 color='#333333'><b>💰 Pagamento à Vista</b></font><br/><br/>"
            f"<font size=10 color='#666666'>Valor base:</font> <font size=10 color='#333333'>R$ {cotacao.valor_parcelado:.2f}</font><br/>"
            f"<font size=10 color='#666666'>Desconto ({cotacao.desconto:.0f}%):</font> <font size=10 color='#333333'>- R$ {desconto_valor:.2f}</font><br/><br/>"
            f"<font size=12 color='#333333'><b>Total à vista:</b></font> <font size=12 color='#333333'><b>R$ {cotacao.valor_vista:.2f}</b></font>"
        ]
    ]
    
    pagamento_table = Table(pagamento_data, colWidths=[8*cm, 8*cm])
    pagamento_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.white),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('INNERGRID', (0, 0), (-1, -1), 1, colors.HexColor('#e9ecef')),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
    ]))
    
    elements.append(pagamento_table)
    elements.append(Spacer(1, 20))

    # === VALIDADE ===
    if cotacao.validade:
        validade_data = [
            [Paragraph(f"⏰ Esta cotação é válida até {cotacao.validade.strftime('%d/%m/%Y')}", 
                      ParagraphStyle('Validade', parent=estilo_normal, textColor=colors.HexColor('#856404'), alignment=TA_CENTER, fontSize=12, fontName='Helvetica-Bold'))]
        ]
        
        validade_table = Table(validade_data, colWidths=[16*cm])
        validade_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#fff3cd')),
            ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#ffeaa7')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 15),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ]))
        
        elements.append(validade_table)
        elements.append(Spacer(1, 20))

    # === RODAPÉ ===
    footer_data = [
        [Paragraph("Esta é uma proposta de cotação. Valores sujeitos à disponibilidade.", 
                  ParagraphStyle('Footer1', parent=estilo_normal, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, fontSize=10))],
        [Paragraph(f"Documento gerado automaticamente em {timezone.now().strftime('%d/%m/%Y')}", 
                  ParagraphStyle('Footer2', parent=estilo_normal, textColor=colors.HexColor('#666666'), alignment=TA_CENTER, fontSize=10))]
    ]
    
    footer_table = Table(footer_data, colWidths=[16*cm])
    footer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#e9ecef')),
    ]))
    
    elements.append(footer_table)

    # Construir o PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


# Função original mantida para compatibilidade
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
