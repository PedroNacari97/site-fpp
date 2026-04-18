from collections import OrderedDict
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class NotificacaoSistemaQuerySet(models.QuerySet):
    def ativas(self):
        return self.filter(arquivada_em__isnull=True)

    def arquivadas(self):
        return self.filter(arquivada_em__isnull=False)

    def nao_lidas(self):
        return self.ativas().filter(lida=False)

    def lidas(self):
        return self.ativas().filter(lida=True)

    def do_usuario(self, usuario):
        if usuario is None or not getattr(usuario, "is_authenticated", False):
            return self.none()
        return self.filter(usuario=usuario)

    def da_empresa(self, empresa):
        if empresa is None:
            return self
        return self.filter(models.Q(empresa=empresa) | models.Q(empresa__isnull=True))


class NotificacaoSistemaManager(models.Manager.from_queryset(NotificacaoSistemaQuerySet)):
    def agrupadas_por_tipo(self, usuario, *, empresa=None, apenas_nao_lidas=True, limite=20):
        """Retorna dict OrderedDict {tipo: {"label": str, "total": int, "nao_lidas": int, "itens": list}}.

        Usado pelo dropdown para mostrar resumos do tipo "3 novas cotações".
        """
        qs = self.do_usuario(usuario).ativas()
        if empresa is not None:
            qs = qs.da_empresa(empresa)
        if apenas_nao_lidas:
            qs = qs.filter(lida=False)
        qs = qs.order_by("-criado_em")[:limite]

        grupos = OrderedDict()
        label_map = dict(NotificacaoSistema.Tipo.choices)
        for item in qs:
            tipo = item.tipo or NotificacaoSistema.Tipo.OUTROS
            entry = grupos.setdefault(
                tipo,
                {
                    "tipo": tipo,
                    "label": label_map.get(tipo, "Notificações"),
                    "total": 0,
                    "nao_lidas": 0,
                    "itens": [],
                },
            )
            entry["total"] += 1
            if not item.lida:
                entry["nao_lidas"] += 1
            entry["itens"].append(item)
        return grupos


class NotificacaoSistema(models.Model):
    class Tipo(models.TextChoices):
        COTACAO_NOVA = "cotacao_nova", "Novas cotações"
        COTACAO_APROVADA = "cotacao_aprovada", "Cotações aprovadas"
        COTACAO_VENCENDO = "cotacao_vencendo", "Cotações vencendo"
        EMISSAO_CONCLUIDA = "emissao_concluida", "Emissões concluídas"
        EMISSAO_PENDENTE = "emissao_pendente", "Emissões pendentes"
        ALERTA_PASSAGEM = "alerta_passagem", "Alertas de passagem"
        CLIENTE_CADASTRADO = "cliente_cadastrado", "Clientes cadastrados"
        CLUBE_VENCENDO = "clube_vencendo", "Clubes vencendo"
        SALDO_BAIXO = "saldo_baixo", "Saldos baixos"
        SISTEMA = "sistema", "Sistema"
        OUTROS = "outros", "Outros"

    # Mapeamento usado para inferir tipo a partir de chaves dinâmicas
    # (mantém compat com build_operational_notifications existente).
    KEY_PREFIX_TO_TIPO = {
        "cotacao_vencendo": Tipo.COTACAO_VENCENDO,
        "cotacao_nova": Tipo.COTACAO_NOVA,
        "cotacao_aprovada": Tipo.COTACAO_APROVADA,
        "emissao_pendente": Tipo.EMISSAO_PENDENTE,
        "emissao_concluida": Tipo.EMISSAO_CONCLUIDA,
        "voo_proximo": Tipo.EMISSAO_PENDENTE,
        "match_alerta": Tipo.ALERTA_PASSAGEM,
        "alerta_recente": Tipo.ALERTA_PASSAGEM,
        "clube_vencendo": Tipo.CLUBE_VENCENDO,
        "saldo_baixo": Tipo.SALDO_BAIXO,
        "cliente_cadastrado": Tipo.CLIENTE_CADASTRADO,
        "sistema": Tipo.SISTEMA,
    }

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notificacoes_sistema",
        null=True,
        blank=True,
    )
    empresa = models.ForeignKey(
        "gestao.Empresa",
        on_delete=models.CASCADE,
        related_name="notificacoes_sistema",
        null=True,
        blank=True,
    )
    tipo = models.CharField(
        max_length=32,
        choices=Tipo.choices,
        default=Tipo.OUTROS,
        db_index=True,
    )
    chave = models.CharField(max_length=191, blank=True, db_index=True)
    titulo = models.CharField(max_length=255, blank=True)
    mensagem = models.TextField(blank=True)
    url = models.CharField(max_length=500, blank=True)
    url_acao = models.CharField(max_length=500, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)
    lida_em = models.DateTimeField(null=True, blank=True)
    arquivada_em = models.DateTimeField(null=True, blank=True, db_index=True)

    objects = NotificacaoSistemaManager()

    class Meta:
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "chave"],
                condition=~models.Q(chave=""),
                name="unique_notificacao_sistema_usuario_chave",
            )
        ]
        indexes = [
            models.Index(fields=["usuario", "lida", "arquivada_em"], name="ns_usuario_lida_arq_idx"),
            models.Index(fields=["tipo", "criado_em"], name="ns_tipo_criado_idx"),
        ]

    def __str__(self):
        return self.titulo or self.chave or "Notificacao"

    # ── Compat ────────────────────────────────────────────────
    @property
    def url_destino(self):
        return self.url_acao or self.url or ""

    # ── Ações ─────────────────────────────────────────────────
    def marcar_lida(self, *, salvar=True):
        if self.lida and self.lida_em:
            return self
        self.lida = True
        self.lida_em = timezone.now()
        if salvar:
            self.save(update_fields=["lida", "lida_em"])
        return self

    def desmarcar_lida(self, *, salvar=True):
        if not self.lida:
            return self
        self.lida = False
        self.lida_em = None
        if salvar:
            self.save(update_fields=["lida", "lida_em"])
        return self

    def arquivar(self, *, salvar=True):
        if self.arquivada_em is not None:
            return self
        self.arquivada_em = timezone.now()
        if not self.lida:
            self.lida = True
            self.lida_em = self.lida_em or self.arquivada_em
        if salvar:
            self.save(update_fields=["arquivada_em", "lida", "lida_em"])
        return self

    @classmethod
    def tipo_da_chave(cls, chave):
        if not chave:
            return cls.Tipo.OUTROS
        prefix = chave.split(":", 1)[0]
        return cls.KEY_PREFIX_TO_TIPO.get(prefix, cls.Tipo.OUTROS)

    @classmethod
    def arquivar_antigas(cls, *, dias=30, agora=None):
        """Arquiva notificações lidas com criado_em < agora - dias. Retorna count."""
        agora = agora or timezone.now()
        limite = agora - timedelta(days=dias)
        qs = cls.objects.filter(
            arquivada_em__isnull=True,
            lida=True,
            criado_em__lt=limite,
        )
        total = qs.count()
        qs.update(arquivada_em=agora)
        return total
