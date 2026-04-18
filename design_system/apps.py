from django.apps import AppConfig


class DesignSystemConfig(AppConfig):
    """App de PREVIEW isolado do design system NCfly.

    Serve as 10 telas do redesign como mockups renderizados pelo Django,
    sem tocar nos apps reais (portal, painel_cliente, gestao, accounts,
    superadmin, onboarding). Nao possui models, migrations ou testes.
    Acesso intencionalmente aberto — usar apenas em dev/staging.
    """

    default_auto_field = "django.db.models.BigAutoField"
    name = "design_system"
    verbose_name = "Design System (preview)"
