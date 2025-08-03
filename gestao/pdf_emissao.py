from io import BytesIO
from decimal import Decimal, InvalidOperation
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

def gerar_pdf_emissao(emissao):
    """
    Gera PDF da emissão com design premium refinado e robusto.
    """

    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25 * mm,
        leftMargin=25 * mm,
        topMargin=20 * mm,
        bottomMargin=25 * mm,
    )

    styles = getSampleStyleSheet()

    # Paleta de cores premium
    cor_primaria = colors.Color(0.15, 0.25, 0.65, 1)
    cor_secundaria = colors.Color(0.2, 0.3, 0.7, 1)
    cor_acento = colors.Color(0.85, 0.65, 0.1, 1)
    cor_sucesso = colors.Color(0.1, 0.5, 0.2, 1)
    cor_alerta = colors.Color(0.7, 0.15, 0.15, 1)
    cor_fundo_claro = colors.Color(0.98, 0.98, 0.99, 1)
    cor_fundo_medio = colors.Color(0.94, 0.95, 0.97, 1)
    cor_texto_principal = colors.Color(0.15, 0.15, 0.2, 1)
    cor_texto_secundario = colors.Color(0.4, 0.4, 0.5, 1)

    # Estilos premium refinados
    titulo_principal = ParagraphStyle(
        'TituloPrincipal',
        parent=styles['Heading1'],
        fontSize=22,
        textColor=colors.white,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold',
        leading=26,
        spaceBefore=0,
        spaceAfter=0
    )

    titulo_secao = ParagraphStyle(
        'TituloSecao',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=cor_primaria,
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold'
    )

    estilo_label = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=9,
        textColor=cor_texto_secundario,
        fontName='Helvetica-Bold',
        alignment=TA_LEFT,
        spaceBefore=1,
        spaceAfter=1
    )

    estilo_valor = ParagraphStyle(
        'Valor',
        parent=styles['Normal'],
        fontSize=11,
        textColor=cor_texto_principal,
        fontName='Helvetica',
        alignment=TA_LEFT,
        spaceBefore=1,
        spaceAfter=6
    )

    estilo_valor_destaque = ParagraphStyle(
        'ValorDestaque',
        parent=estilo_valor,
        fontSize=12,
        textColor=cor_sucesso,
        fontName='Helvetica-Bold'
    )

    estilo_link = ParagraphStyle(
        'Link',
        parent=estilo_valor,
        textColor=cor_secundaria,
        underline=True,
    )

    elements = []

    # CABEÇALHO
    header_data = [
        [Paragraph("Confirmação de Emissão de Passagem", titulo_principal)]
    ]
    header_table = Table(header_data, colWidths=[160*mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_primaria),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 15),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 15),
        ('LEFTPADDING', (0, 0), (-1, -1), 20),
        ('RIGHTPADDING', (0, 0), (-1, -1), 20),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 6),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 25))

    # INFORMAÇÕES DO CLIENTE
    elements.append(Paragraph("Informações do Cliente", titulo_secao))
    cliente_nome = (
        getattr(getattr(emissao, 'cliente', None), 'usuario', None)
        and (emissao.cliente.usuario.get_full_name() or emissao.cliente.usuario.username)
    ) or "-"
    cliente_doc = getattr(getattr(emissao, 'cliente', None), 'documento', None) or "-"
    cliente_data = [
        [Paragraph("NOME COMPLETO", estilo_label), Paragraph("DOCUMENTO", estilo_label)],
        [Paragraph(cliente_nome, estilo_valor), Paragraph(cliente_doc, estilo_valor)]
    ]
    cliente_table = Table(cliente_data, colWidths=[80*mm, 80*mm])
    cliente_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo_claro),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, cor_texto_secundario),
    ]))
    elements.append(cliente_table)
    elements.append(Spacer(1, 20))

    # DADOS DA EMISSÃO
    elements.append(Paragraph("Dados da Emissão", titulo_secao))
    companhia = getattr(emissao, "companhia_aerea", None)
    if hasattr(companhia, "nome"):
        companhia_nome = companhia.nome
        companhia_link = getattr(companhia, "site_url", None)
    elif isinstance(companhia, str):
        companhia_nome = companhia
        companhia_link = None
    else:
        companhia_nome = "-"
        companhia_link = None
    if companhia_link:
        companhia_para_pdf = Paragraph(f'<a href="{companhia_link}">{companhia_nome}</a>', estilo_link)
    else:
        companhia_para_pdf = Paragraph(companhia_nome, estilo_valor)

    data_ida = getattr(emissao, 'data_ida', None)  # datetime
    data_ida_str = data_ida.strftime("%d/%m/%Y às %H:%M") if data_ida else "-"

    programa_nome = getattr(getattr(emissao, 'programa', None), 'nome', None) or "-"
    localizador = getattr(emissao, 'localizador', None) or "-"
    emissao_data = [
        [Paragraph("COMPANHIA AÉREA", estilo_label), Paragraph("DATA DE EMISSÃO", estilo_label)],
        [companhia_para_pdf, Paragraph(data_ida_str, estilo_valor)],
        [Paragraph("PROGRAMA DE FIDELIDADE", estilo_label), Paragraph("LOCALIZADOR", estilo_label)],
        [Paragraph(programa_nome, estilo_valor), Paragraph(localizador, ParagraphStyle(
            'Localizador', parent=estilo_valor, fontSize=12, fontName='Helvetica-Bold', textColor=cor_acento
        ))]
    ]
    emissao_table = Table(emissao_data, colWidths=[80*mm, 80*mm])
    emissao_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo_claro),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, cor_texto_secundario),
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, cor_texto_secundario),
    ]))
    elements.append(emissao_table)
    elements.append(Spacer(1, 20))

    # INFORMAÇÕES FINANCEIRAS
    elements.append(Paragraph("Informações Financeiras", titulo_secao))
    valor_pago = getattr(emissao, 'valor_pago', Decimal('0'))
    try:
        valor_pago = Decimal(valor_pago)
    except (InvalidOperation, TypeError):
        valor_pago = Decimal('0')
    valor_referencia = getattr(emissao, 'valor_referencia', None)
    try:
        valor_referencia = Decimal(valor_referencia) if valor_referencia else valor_pago * Decimal('1.3')
    except (InvalidOperation, TypeError):
        valor_referencia = valor_pago * Decimal('1.3')
    valor_economizado = valor_referencia - valor_pago
    percentual_economia = (valor_economizado / valor_referencia * 100) if valor_referencia > 0 else Decimal('0')

    financeiro_data = [
        [Paragraph("VALOR DE REFERÊNCIA", estilo_label), Paragraph("VALOR TOTAL PAGO", estilo_label)],
        [Paragraph(f"R$ {valor_referencia:.2f}", estilo_valor),
         Paragraph(f"R$ {valor_pago:.2f}", estilo_valor_destaque)],
        [Paragraph("VALOR ECONOMIZADO", estilo_label), Paragraph("PERCENTUAL DE ECONOMIA", estilo_label)],
        [Paragraph(f"R$ {valor_economizado:.2f}", ParagraphStyle(
            'Economia', parent=estilo_valor, textColor=cor_alerta, fontSize=12, fontName='Helvetica-Bold')),
         Paragraph(f"{percentual_economia:.0f}%", ParagraphStyle(
             'PercentEconomia', parent=estilo_valor, textColor=cor_alerta, fontSize=12, fontName='Helvetica-Bold'))]
    ]
    financeiro_table = Table(financeiro_data, colWidths=[80*mm, 80*mm])
    financeiro_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 1), cor_fundo_claro),
        ('BACKGROUND', (0, 2), (-1, -1), colors.Color(0.99, 0.96, 0.96, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, cor_texto_secundario),
        ('LINEBELOW', (0, 1), (-1, 1), 1, cor_fundo_medio),
        ('LINEBELOW', (0, 2), (-1, 2), 0.5, cor_texto_secundario),
    ]))
    elements.append(financeiro_table)
    elements.append(Spacer(1, 20))

    # --- INFORMAÇÕES DO VOO (DATA E HORA LADO A LADO, PADRÃO BR) ---
    aeroporto_partida = getattr(emissao, 'aeroporto_partida', None)
    aeroporto_destino = getattr(emissao, 'aeroporto_destino', None)
    origem_str = (
        f"{getattr(aeroporto_partida, 'sigla', '-')}" +
        (f" - {getattr(aeroporto_partida, 'nome', '-')}" if aeroporto_partida else "")
    ) if aeroporto_partida else "-"
    destino_str = (
        f"{getattr(aeroporto_destino, 'sigla', '-')}" +
        (f" - {getattr(aeroporto_destino, 'nome', '-')}" if aeroporto_destino else "")
    ) if aeroporto_destino else "-"

    data_ida = getattr(emissao, 'data_ida', None)
    data_volta = getattr(emissao, 'data_volta', None)
    data_ida_str = data_ida.strftime("%d/%m/%Y às %H:%M") if data_ida else "-"
    data_volta_str = data_volta.strftime("%d/%m/%Y às %H:%M") if data_volta else "-"

    voo_data = [
        [Paragraph("ORIGEM", estilo_label), Paragraph("DESTINO", estilo_label)],
        [Paragraph(origem_str, estilo_valor), Paragraph(destino_str, estilo_valor)],
        [Paragraph("DATA E HORA DE IDA", estilo_label), Paragraph("DATA E HORA DE VOLTA", estilo_label)],
        [Paragraph(data_ida_str, estilo_valor), Paragraph(data_volta_str, estilo_valor)],
    ]
    voo_table = Table(voo_data, colWidths=[80*mm, 80*mm])
    voo_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo_claro),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, cor_texto_secundario),
    ]))
    elements.append(PageBreak())
    elements.append(Paragraph("Informações do Voo", titulo_secao))
    elements.append(voo_table)
    elements.append(Spacer(1, 20))

# Escalas (após tabela de voo)
    escalas = getattr(emissao, "escalas", None)
    if escalas and hasattr(escalas, "exists") and escalas.exists():
        for escala in escalas.all():
            escala_aeroporto = getattr(escala, 'aeroporto', None)
            aeroporto_escala_str = (
            f"{getattr(escala_aeroporto, 'sigla', '-')}" +
            (f" - {getattr(escala_aeroporto, 'nome', '-')}" if escala_aeroporto else "")
        ) if escala_aeroporto else "-"

        duracao_escala = getattr(escala, 'duracao', None)
        duracao_escala_str = str(duracao_escala) if duracao_escala else "-"

        escala_data = [
            [Paragraph("AEROPORTO DE ESCALA", estilo_label), Paragraph("DURAÇÃO DA ESCALA", estilo_label)],
            [Paragraph(aeroporto_escala_str, estilo_valor), Paragraph(duracao_escala_str, estilo_valor)],
        ]

        escala_table = Table(escala_data, colWidths=[80*mm, 80*mm])
        escala_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), cor_fundo_claro),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('LEFTPADDING', (0, 0), (-1, -1), 12),
            ('RIGHTPADDING', (0, 0), (-1, -1), 12),
            ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, 0), 0.5, cor_texto_secundario),
        ]))
        elements.append(escala_table)
        elements.append(Spacer(1, 5))


    # PASSAGEIROS
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("Passageiros", titulo_secao))

    total_passageiros = f"Adultos: {getattr(emissao, 'qtd_adultos', 0)} | Crianças: {getattr(emissao, 'qtd_criancas', 0)} | Bebês: {getattr(emissao, 'qtd_bebes', 0)}"
    total_data = [
        [Paragraph("TOTAL DE PASSAGEIROS", estilo_label)],
        [Paragraph(total_passageiros, ParagraphStyle(
            'TotalPassageiros', parent=estilo_valor, fontSize=11, fontName='Helvetica-Bold', textColor=cor_texto_principal
        ))]
    ]
    total_table = Table(total_data, colWidths=[160*mm])
    total_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.Color(0.96, 0.97, 0.99, 1)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, 0), 0.5, cor_texto_secundario),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 10))

    # Tabela de passageiros
    passageiros_data = [
        [Paragraph("Nome", ParagraphStyle('HeaderTabela', parent=estilo_label, textColor=colors.white, fontSize=10, fontName='Helvetica-Bold')),
         Paragraph("Documento", ParagraphStyle('HeaderTabela', parent=estilo_label, textColor=colors.white, fontSize=10, fontName='Helvetica-Bold'))]
    ]
    categorias = [
        ("adulto", "Adultos"),
        ("crianca", "Crianças"),
        ("bebe", "Bebês"),
    ]
    linha_categoria_indices = [0]
    for chave, titulo in categorias:
        passageiros = getattr(emissao, 'passageiros', None)
        if passageiros and hasattr(passageiros, 'filter'):
            passageiros_qs = passageiros.filter(categoria=chave)
            if hasattr(passageiros_qs, 'exists') and passageiros_qs.exists():
                linha_categoria_indices.append(len(passageiros_data))
                passageiros_data.append([Paragraph(titulo, ParagraphStyle(
                    'Categoria', parent=estilo_valor, fontName='Helvetica-Bold', fontSize=10, textColor=cor_primaria)), ""])
                for p in passageiros_qs:
                    nome = getattr(p, 'nome', '-') or '-'
                    documento = getattr(p, 'documento', '-') or '-'
                    passageiros_data.append([Paragraph(nome, estilo_valor), Paragraph(documento, estilo_valor)])

    passageiros_table = Table(passageiros_data, colWidths=[100*mm, 60*mm])
    table_style = [
        ('BACKGROUND', (0, 0), (-1, 0), cor_primaria),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.3, cor_fundo_medio),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
    ]
    # Destacar linhas de categoria
    for idx in linha_categoria_indices[1:]:
        table_style.append(('BACKGROUND', (0, idx), (-1, idx), cor_fundo_medio))
        table_style.append(('FONTNAME', (0, idx), (-1, idx), 'Helvetica-Bold'))
    passageiros_table.setStyle(TableStyle(table_style))
    elements.append(passageiros_table)

    detalhes = getattr(emissao, "detalhes", None)
    if detalhes and str(detalhes).strip():
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("Observações da Emissão", titulo_secao))
        detalhes_texto = str(detalhes).strip().replace('\n', '<br/>')
    # Usando Table para padronizar borda, fundo e espaçamento
        detalhes_table = Table(
    [[Paragraph(detalhes_texto, estilo_valor)]],
        colWidths=[160 * mm]
    )
    detalhes_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo_claro),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('LEFTPADDING', (0, 0), (-1, -1), 12),
        ('RIGHTPADDING', (0, 0), (-1, -1), 12),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, cor_texto_secundario),
    ]))
    elements.append(detalhes_table)




    # Rodapé premium, com data/hora no padrão BR
    elements.append(Spacer(1, 30))
    rodape_data = [
        [Paragraph(
            "Este documento confirma a emissão do bilhete. Guarde-o para referência.",
            ParagraphStyle(
                'RodapeTexto', parent=estilo_valor, alignment=TA_CENTER,
                fontSize=10, textColor=cor_texto_principal, fontName='Helvetica-Bold'
            )
        )],
        [Paragraph(
            f"Gerado em {timezone.localtime().strftime('%d/%m/%Y às %H:%M')}",
            ParagraphStyle(
                'RodapeData', parent=estilo_valor, alignment=TA_CENTER,
                fontSize=9, textColor=cor_texto_secundario
            )
        )]
    ]
    rodape_table = Table(rodape_data, colWidths=[160*mm])
    rodape_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), cor_fundo_claro),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('LEFTPADDING', (0, 0), (-1, -1), 15),
        ('RIGHTPADDING', (0, 0), (-1, -1), 15),
        ('ROUNDEDCORNERS', (0, 0), (-1, -1), 3),
        ('LINEABOVE', (0, 0), (-1, 0), 1.5, cor_primaria),
    ]))
    elements.append(rodape_table)

    # Geração do PDF
    doc.build(elements)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
