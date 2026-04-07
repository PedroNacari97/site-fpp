from django.http import FileResponse
from io import BytesIO
from gestao.pdf_cotacao import gerar_pdf_cotacao
from gestao.pdf_emissao import gerar_pdf_emissao
from gestao.services.cotacao_preview import build_cotacao_preview_context
from gestao.services.emissao_preview import build_emissao_preview_context
from services.browser_pdf import render_pdf_from_template


def emissao_pdf_response(emissao, *, filename_prefix="emissao", as_attachment=True):
    """Return an HTTP response with the generated emission PDF.

    This service centralises the PDF generation logic for emissions, keeping
    the view layer thin and focused on HTTP concerns.
    """
    try:
        pdf = render_pdf_from_template(
            "admin_custom/pdf/emissao_preview_pdf.html",
            {
                "emissao": emissao,
                "preview": build_emissao_preview_context(emissao, for_pdf=True),
            },
            css_paths=(
                "gestao/css/base/variables.css",
                "gestao/css/cotacao_preview.css",
                "gestao/css/emissao_preview.css",
            ),
        )
    except Exception:
        pdf = gerar_pdf_emissao(emissao)

    buffer = BytesIO(pdf)
    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=as_attachment,
        filename=f"{filename_prefix}_{emissao.id}.pdf",
    )


def cotacao_pdf_response(cotacao, *, filename_prefix="cotacao", as_attachment=True):
    """Return a FileResponse with the generated quotation PDF.

    The PDF content is generated using the existing generator while this
    service wraps the creation of the file response.
    """
    try:
        pdf_content = render_pdf_from_template(
            "admin_custom/pdf/cotacao_voo_pdf.html",
            {
                "cotacao": cotacao,
                **build_cotacao_preview_context(cotacao, for_pdf=True),
            },
            css_paths=(
                "gestao/css/base/variables.css",
                "gestao/css/cotacao_preview.css",
                "gestao/css/emissao_preview.css",
            ),
        )
    except Exception:
        pdf_content = gerar_pdf_cotacao(cotacao)

    buffer = BytesIO(pdf_content)
    buffer.seek(0)
    return FileResponse(
        buffer,
        as_attachment=as_attachment,
        filename=f"{filename_prefix}_{cotacao.id}.pdf",
    )
