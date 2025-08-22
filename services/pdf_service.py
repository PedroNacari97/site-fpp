from django.http import FileResponse, HttpResponse
from io import BytesIO
from gestao.pdf_cotacao import gerar_pdf_cotacao
from gestao.pdf_emissao import gerar_pdf_emissao


def emissao_pdf_response(emissao):
    """Return an HTTP response with the generated emission PDF.

    This service centralises the PDF generation logic for emissions, keeping
    the view layer thin and focused on HTTP concerns.
    """
    pdf = gerar_pdf_emissao(emissao)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="emissao_{emissao.id}.pdf"'  # noqa: E501
    )
    return response


def cotacao_pdf_response(cotacao, *, filename_prefix="cotacao"):
    """Return a FileResponse with the generated quotation PDF.

    The PDF content is generated using the existing generator while this
    service wraps the creation of the file response.
    """
    pdf_content = gerar_pdf_cotacao(cotacao)
    buffer = BytesIO(pdf_content)
    return FileResponse(
        buffer,
        as_attachment=True,
        filename=f"{filename_prefix}_{cotacao.id}.pdf",
    )
