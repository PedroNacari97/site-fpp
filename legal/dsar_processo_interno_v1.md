# Processo Interno de Atendimento a Titulares (DSAR) — NC Fly

> **Versão:** v1.0
> **Vigência:** a partir da aprovação do DPO
> **Base legal:** Lei 13.709/2018 (LGPD), art. 18 a 22; Resoluções da ANPD
> sobre direitos do titular e sobre incidentes de segurança.

Este documento é de uso **interno** da NC Fly. Não deve ser publicado. Serve
de *runbook* para operadores, DPO e equipe de suporte ao receber pedidos de
titulares de dados pessoais.

---

## 1. Canal oficial de entrada

- **E-mail DPO:** `{{ PORTAL_DPO_EMAIL }}` (configurado em `core/settings.py`).
- **Formulário público:** `/fale-conosco/#privacidade` (seção "Direitos do
  titular de dados (LGPD)" do template `portal/fale_conosco.html`).
- Pedidos chegados por outros canais (WhatsApp, Instagram DM, suporte geral)
  devem ser **encaminhados ao DPO** em até 24h úteis.

## 2. Tipos de pedido suportados (LGPD art. 18)

| Código | Direito | Onde buscar os dados |
|---|---|---|
| DSAR-01 | Confirmação de tratamento | `User`, `Cliente`, `LeadAlertaEmail`, `LeadPlataforma`, `AceiteDocumentoPlataforma`, `PortalMetricDaily` |
| DSAR-02 | Acesso (cópia) | idem |
| DSAR-03 | Correção | editar nos mesmos models |
| DSAR-04 | Anonimização / bloqueio / exclusão | ver cláusula 5 abaixo |
| DSAR-05 | Portabilidade | exportar JSON/CSV dos registros |
| DSAR-06 | Informação sobre compartilhamento | listar suboperadores (Railway, Resend, gateway, Cloudflare) |
| DSAR-07 | Revogação de consentimento | alertas: usar link de unsubscribe; cookies: painel de preferências |
| DSAR-08 | Oposição a tratamento | avaliar base legal (legítimo interesse / obrigação legal) |
| DSAR-09 | Revisão de decisão automatizada | atualmente **não aplicável** — NC Fly não toma decisões automatizadas com efeitos jurídicos sobre titulares |

## 3. SLA interno de resposta

- **Acuse de recebimento:** até **2 dias úteis**.
- **Resposta formal:** até **15 dias corridos** da ciência do pedido completo,
  prorrogáveis de forma motivada por mais 15 dias (modelo ANPD).
- **Recusa motivada:** obrigatório citar a base legal e informar o direito
  de peticionar à ANPD.

## 4. Verificação de identidade

Exigir mínimo:
- Para cadastros de **alerta por e-mail**: confirmar pelo próprio e-mail
  cadastrado, respondendo de `LeadAlertaEmail.email` ativo.
- Para **clientes da plataforma B2B**: confirmar com login + dois itens
  cadastrais (CPF parcial + telefone, por ex.) e, para exclusões totais,
  exigir manifestação do *admin* da `Empresa`.
- Nunca compartilhar dados com terceiros sem ordem judicial.

## 5. Exclusão e retenção

Ao processar DSAR-04:

- **Alertas por e-mail:** marcar `LeadAlertaEmail.status = STATUS_DESCADASTRADO`,
  preencher `cancelado_em` e `motivo_cancelamento`. Manter registro mínimo
  para prova de consentimento revogado (art. 16, LGPD — exercício regular
  de direitos).
- **Leads da plataforma (`LeadPlataforma`):** status `arquivado`; anonimizar
  `email`, `telefone`, `mensagem` após **6 meses** sem conversão.
- **Clientes ativos (`Cliente`, `User`):** só excluir após encerrar
  `Assinatura`, exportar os dados operacionais para a CONTRATANTE (titular
  empresarial dos dados) e aguardar prazos legais (fiscal = 5 anos;
  civil = 10 anos).
- **Logs de segurança (`SecurityEvent`, `LoginGuard`):** retenção padrão
  **12 meses** (Marco Civil art. 15 = 6 meses para logs de acesso; mantemos
  maior por prevenção de fraude). Registrar base legal: legítimo interesse.
- **Aceites (`AceiteDocumentoPlataforma`):** **não excluir** enquanto o
  contrato estiver vigente + 5 anos após o encerramento. Hash + IP + UA são
  prova jurídica do consentimento.

## 6. Registro e auditoria do atendimento

Todo pedido deve gerar entrada em uma planilha/issue interna com:
- Código DSAR
- Data de recebimento
- Identificação (ou hash) do titular
- Direito exercido
- Ação tomada + data
- Responsável (DPO ou delegado)
- Prazo de resposta cumprido (s/n)

Exportar relatório consolidado **trimestralmente** para o DPO.

## 7. Escalonamento

- **Dados sensíveis** (saúde, biometria, menor de idade): escalar para
  advogado humano antes de resposta.
- **Pedido de exclusão que afete contrato vigente com empresa B2B:**
  notificar o *admin* da `Empresa` antes de executar (NC Fly atua como
  operadora; cabe ao controlador decidir).
- **Incidente de segurança** descoberto durante o atendimento: acionar o
  playbook de incidentes (DPA cláusula 7, prazo 72h para notificar ANPD
  quando aplicável).

## 8. Templates de resposta

Manter em `/legal/templates_dsar/` (pendente):
- `dsar_acuse_recebimento.md`
- `dsar_resposta_acesso.md`
- `dsar_resposta_exclusao.md`
- `dsar_recusa_motivada.md`

---

**Responsável pelo processo:** DPO — `{{ PORTAL_DPO_EMAIL }}`.
**Revisão anual obrigatória** deste documento.
