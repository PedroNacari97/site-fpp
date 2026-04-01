def _clean_text(value, fallback="Sob consulta"):
    text = str(value or "").strip()
    return text or fallback


def _display_website(value):
    website = str(value or "").strip()
    if not website:
        return "Sob consulta"
    return website.replace("https://", "").replace("http://", "").rstrip("/")


def get_empresa_from_operational_record(record):
    cliente = getattr(record, "cliente", None)
    if cliente and getattr(cliente, "empresa", None):
        return cliente.empresa

    conta_administrada = getattr(record, "conta_administrada", None)
    if conta_administrada and getattr(conta_administrada, "empresa", None):
        return conta_administrada.empresa

    return None


def build_empresa_contact_context(empresa):
    admin = getattr(empresa, "admin", None) if empresa else None
    admin_user = getattr(admin, "usuario", None) if admin else None
    admin_name = ""
    admin_email = ""

    if admin_user:
        admin_name = admin_user.get_full_name() or admin_user.username or ""
        admin_email = getattr(admin_user, "email", "") or ""

    return {
        "empresa_nome": _clean_text(getattr(empresa, "nome", ""), fallback="NC Fly"),
        "responsavel_nome": _clean_text(
            getattr(empresa, "responsavel_nome", "") or admin_name,
            fallback="Equipe NC Fly",
        ),
        "telefone": _clean_text(
            getattr(empresa, "telefone_contato", "") or getattr(empresa, "whatsapp", "")
        ),
        "email": _clean_text(getattr(empresa, "email_contato", "") or admin_email),
        "website": _display_website(getattr(empresa, "website", "")),
        "endereco": _clean_text(
            " - ".join(
                part
                for part in [
                    str(getattr(empresa, "endereco", "") or "").strip(),
                    str(getattr(empresa, "cidade", "") or "").strip(),
                    str(getattr(empresa, "estado", "") or "").strip(),
                ]
                if part
            ),
            fallback="Endereco sob consulta",
        ),
        "descricao_rodape": _clean_text(
            getattr(empresa, "descricao_rodape", ""),
            fallback="Atendimento especializado em emissao, milhas e viagens.",
        ),
    }
