# CONTRATO DE PRESTAÇÃO DE SERVIÇOS DE SOFTWARE COMO SERVIÇO (SaaS)
## Plataforma NC Fly — Versão 1.0

> **Versão:** v1.0
> **Vigência:** a definir pela CONTRATANTE na aprovação
> **Base documental:** este texto consolida as cláusulas já publicadas em
> `/plataforma/termos-de-uso/`, `/plataforma/privacidade/`, `/plataforma/dpa/` e
> `/plataforma/seguranca/`, e serve de anexo para assinatura com empresas que
> contratarem a plataforma fora do fluxo de onboarding digital (contratos
> corporativos, planos customizados, clientes enterprise).
>
> **[ATENÇÃO]** Os valores entre `{{ … }}` e marcadores `[DECISÃO]` dependem
> de decisão do dono do negócio antes de assinatura.

---

### 1. PARTES

1.1. **CONTRATADA:** `{{ razão social da NC Fly }}`, inscrita no CNPJ sob o nº
`{{ CNPJ }}`, com sede em `{{ endereço }}`, neste ato representada na forma do
seu contrato social ("NC Fly").

1.2. **CONTRATANTE:** pessoa jurídica (ou pessoa física equiparada no regime
de autônomo profissional) identificada no Anexo I deste instrumento, nos
termos do cadastro realizado na plataforma.

1.3. As partes declaram capacidade civil e poderes para contratar e se
obrigam pelos termos deste instrumento e dos documentos listados no item 14.

---

### 2. OBJETO

2.1. A NC Fly concede à CONTRATANTE, pelo prazo deste contrato, **licença de
uso não exclusiva, intransferível e não sublicenciável** da plataforma
NC Fly ("Plataforma"), em ambiente multitenant, destinada à gestão de
cotações, emissões, clientes, passageiros, programas de fidelidade, alertas
e funcionalidades correlatas ao mercado de agências de viagens.

2.2. A Plataforma é disponibilizada sob modelo *Software as a Service (SaaS)*.
A CONTRATANTE **não adquire cópia do código-fonte** nem direito de
modificá-lo, redistribuí-lo ou licenciá-lo a terceiros.

2.3. O escopo de funcionalidades, limites de usuários e clientes é o
definido no plano contratado (Anexo I).

---

### 3. PRAZO, RENOVAÇÃO E RESCISÃO

3.1. **Prazo inicial:** 12 (doze) meses contados da ativação pós-trial,
renovado automaticamente por iguais períodos, salvo denúncia por qualquer
das partes com antecedência mínima de 30 (trinta) dias do término da
vigência.

3.2. **Trial gratuito:** período de `{{ trial_dias }}` dias, sem cobrança,
ao final do qual a CONTRATANTE pode optar por contratar ou extinguir sem
ônus.

3.3. **Rescisão imotivada pela CONTRATANTE** durante a vigência implica
multa compensatória equivalente a **[DECISÃO] 30% (trinta por cento)** do
valor das mensalidades remanescentes até o termo final, sem prejuízo de
valores já vencidos.

3.4. **Rescisão por justa causa** por qualquer das partes, sem multa, em
caso de: (i) inadimplemento não sanado em 15 dias após notificação;
(ii) decretação de falência ou recuperação judicial; (iii) violação grave
de confidencialidade, LGPD ou propriedade intelectual; (iv) uso da
Plataforma para finalidade ilícita.

3.5. **Exportação de dados pós-rescisão:** a CONTRATANTE terá **30 (trinta)
dias** a contar do encerramento para exportar seus dados em formato
estruturado (CSV/JSON). Após esse prazo, os dados operacionais serão
excluídos em **até 90 (noventa) dias**, ressalvados backups e registros de
auditoria mantidos por obrigação legal ou exercício regular de direitos.

---

### 4. PREÇO, REAJUSTE E PAGAMENTO

4.1. A CONTRATANTE pagará à NC Fly o valor mensal do plano contratado,
conforme Anexo I, por meio dos gateways disponibilizados (cartão, PIX,
boleto).

4.2. **Reajuste anual:** os valores serão reajustados anualmente pela
variação positiva acumulada do **IPCA/IBGE** nos 12 meses anteriores à data
de aniversário do contrato. Na ausência ou extinção do IPCA, aplicar-se-á
o índice que vier a substituí-lo oficialmente, ou, subsidiariamente, o
**IGP-M**.

4.3. **Inadimplência:** atrasos implicam juros de mora de 1% ao mês e multa
de 2%. A partir do **15º dia** de atraso a NC Fly poderá **suspender o
acesso** à Plataforma, mediante notificação prévia de 3 dias úteis. A
partir de **30 dias**, poderá rescindir o contrato por justa causa.

4.4. **Reembolso:** não há reembolso proporcional em caso de rescisão pela
CONTRATANTE dentro do ciclo de cobrança vigente, salvo:
(i) indisponibilidade comprovada da Plataforma por período superior ao
previsto no SLA (cláusula 5); (ii) descumprimento grave pela NC Fly.

---

### 5. NÍVEL DE SERVIÇO (SLA)

5.1. **Disponibilidade mensal:** a NC Fly envidará esforços para manter a
Plataforma disponível em **99,5% (noventa e nove vírgula cinco por cento)**
do tempo, medido mensalmente, desconsideradas as janelas de manutenção
programadas e os casos de força maior.

5.2. **Janela de manutenção:** preferencialmente madrugada (23h–05h horário
de Brasília), domingos, com comunicação prévia de 48 horas para paradas
superiores a 30 minutos.

5.3. **Suporte:** canal de e-mail `{{ contato.suporte }}` em dias úteis, das
09h às 18h (horário de Brasília). Tempo alvo de primeira resposta para
incidentes classificados como críticos: até **4 horas úteis**.

5.4. **Penalidade por descumprimento:** indisponibilidade mensal superior
a 1% acima do SLA gera **crédito em mensalidade** (service credit)
equivalente a **5% do valor mensal** para cada ponto percentual excedente,
limitado a 30% do valor mensal.

---

### 6. RESPONSABILIDADE E LIMITAÇÃO

6.1. A NC Fly **não é companhia aérea, banco emissor, programa de
fidelidade, operadora de turismo nem agência**. A Plataforma é ferramenta
de gestão; qualquer decisão comercial, emissão, transferência de pontos ou
negociação com terceiros é de responsabilidade exclusiva da CONTRATANTE.

6.2. A CONTRATANTE é responsável por:
(a) veracidade dos dados inseridos;
(b) base legal do tratamento de dados de seus clientes e passageiros;
(c) guarda de credenciais de acesso e ações dos operadores por ela
convidados;
(d) conformidade da sua operação com a legislação aplicável (CDC, LGPD,
Código Civil, ANAC, Receita Federal etc.).

6.3. **Limitação de responsabilidade:** ressalvadas as hipóteses de dolo,
culpa grave e violação de dados pessoais por falha exclusiva da NC Fly, a
responsabilidade agregada da NC Fly limita-se ao **[DECISÃO] valor
equivalente a 12 (doze) mensalidades do plano contratado**, vigentes na
data do evento.

6.4. A NC Fly não responde por:
(i) indisponibilidade de serviços de terceiros (companhias, GDS, gateways,
provedores de infraestrutura);
(ii) alterações unilaterais feitas por programas de fidelidade ou
companhias aéreas em preços, disponibilidade, regras ou estoques;
(iii) perdas indiretas, lucros cessantes, dano reputacional ou perda de
chance;
(iv) uso indevido da Plataforma por operadores autorizados pela
CONTRATANTE.

---

### 7. PROTEÇÃO DE DADOS (LGPD) — DPA

7.1. Fica integrado a este contrato, como parte indissociável, o
**Aditivo de Tratamento de Dados Pessoais (DPA)** publicado em
`/plataforma/dpa/`, na versão vigente.

7.2. Papéis:
- CONTRATANTE = **CONTROLADORA** dos dados de seus clientes, passageiros
  e colaboradores;
- NC Fly = **OPERADORA** em relação a esses dados;
- NC Fly = **CONTROLADORA INDEPENDENTE** em relação a acesso autenticado,
  logs de segurança, auditoria, cobrança e dados próprios de conta.

7.3. **Suboperadores autorizados (baseline):**
`{{ lista_suboperadores }}` — tipicamente: Railway (hospedagem), Resend
(envio de e-mail), gateway de pagamento, Cloudflare Turnstile (antifraude),
e eventuais provedores de métricas consentidas.

7.4. **Transferência internacional:** a CONTRATANTE reconhece que parte da
infraestrutura pode operar fora do Brasil (Railway, Resend). A NC Fly
adota medidas contratuais compatíveis com o art. 33 da LGPD.

7.5. **Incidente de segurança:** a NC Fly comunicará a CONTRATANTE em até
**72 (setenta e duas) horas** da ciência formal de incidente com potencial
impacto a dados pessoais sob controle da CONTRATANTE, fornecendo as
informações razoavelmente necessárias para que ela cumpra seus deveres de
notificação à ANPD e aos titulares.

7.6. **Encarregado (DPO) da NC Fly:** `{{ portal_dpo_email }}`.

---

### 8. CONFIDENCIALIDADE

8.1. Cada parte se compromete a manter sigilo sobre informações não
públicas da outra parte, inclusive dados operacionais, comerciais,
estratégicos e técnicos, por prazo de **5 (cinco) anos** após o término do
contrato.

8.2. Não se sujeita a este dever a informação: (i) de domínio público sem
culpa da parte receptora; (ii) já conhecida comprovadamente antes da
divulgação; (iii) exigida por ordem judicial ou autoridade competente,
observada a comunicação prévia quando possível.

---

### 9. PROPRIEDADE INTELECTUAL

9.1. O código-fonte, o *design*, a marca NC Fly, a estrutura de dados, as
APIs, a documentação e todos os elementos originais da Plataforma são
propriedade exclusiva da NC Fly.

9.2. Os **dados operacionais inseridos pela CONTRATANTE** permanecem de
sua propriedade; a NC Fly detém licença limitada para hospedá-los,
processá-los e disponibilizá-los dentro da finalidade da Plataforma.

9.3. **Engenharia reversa, descompilação, extração massiva, scraping e
re-hospedagem** são expressamente vedados.

---

### 10. SUSPENSÃO E BLOQUEIO

10.1. A NC Fly pode suspender o acesso da CONTRATANTE em caso de:
(a) inadimplemento (cláusula 4.3); (b) uso indevido, fraudulento ou
ilícito; (c) risco iminente à segurança da Plataforma ou de terceiros;
(d) determinação de autoridade competente.

10.2. Sempre que possível, a suspensão será precedida de notificação com
prazo razoável para regularização, salvo em situações emergenciais de
segurança.

---

### 11. FORÇA MAIOR

11.1. Nenhuma das partes responderá por descumprimento decorrente de caso
fortuito ou força maior (art. 393 do Código Civil), incluindo indisponibilidade
de infraestrutura crítica de terceiros, ataques cibernéticos massivos
contra a internet, eventos climáticos severos, determinações governamentais
extraordinárias e similares.

---

### 12. CESSÃO

12.1. A CONTRATANTE **não poderá ceder** este contrato a terceiros sem
prévia e expressa anuência da NC Fly, sob pena de rescisão por justa causa.

12.2. A NC Fly poderá ceder este contrato em caso de reorganização
societária, fusão, aquisição ou alienação de unidade de negócio, mediante
comunicação à CONTRATANTE.

---

### 13. DISPOSIÇÕES GERAIS

13.1. **Integração:** este contrato, seus anexos e os documentos listados
em 14 constituem o acordo integral entre as partes, prevalecendo sobre
quaisquer entendimentos anteriores.

13.2. **Alterações:** serão válidas quando feitas por escrito, inclusive
por aceite eletrônico registrado na forma da cláusula 14.

13.3. **Nulidade parcial:** a eventual nulidade de uma cláusula não afeta
as demais, que permanecerão em pleno vigor.

13.4. **Foro:** **[DECISÃO] Comarca de `{{ cidade_sede_NC_Fly }}`**,
com renúncia expressa a qualquer outro por mais privilegiado que seja,
para dirimir questões oriundas deste contrato.

13.5. **Cláusula de arbitragem (opcional):** **[ATENÇÃO HUMANA]** avaliar
com advogado se o perfil das CONTRATANTES (PMEs) justifica incluir
arbitragem, considerando custo e acessibilidade.

---

### 14. ACEITE ELETRÔNICO E DOCUMENTOS INTEGRANTES

14.1. Integram este contrato, para todos os fins, as versões vigentes
(disponíveis em URL pública e versionadas) dos documentos:
- Termos da Plataforma — `/plataforma/termos-de-uso/`
- Política de Privacidade da Plataforma — `/plataforma/privacidade/`
- Aditivo de Tratamento de Dados (DPA) — `/plataforma/dpa/`
- Política de Segurança e Uso Aceitável — `/plataforma/seguranca/`

14.2. **Validade do aceite eletrônico** (Lei 14.063/2020 e CC art. 107):
a CONTRATANTE manifesta sua vontade de contratar por meio de **aceite
digital** registrado pela NC Fly no modelo `AceiteDocumentoPlataforma`
(gestao.models), que grava: IP, *user-agent*, *timestamp*, versão aceita,
hash SHA-256 do conteúdo, tipo de dispositivo, navegador, sistema
operacional, fuso, resolução e, se autorizada, geolocalização.

14.3. Cópia dos documentos aceitos, com versão e data, será enviada ao
e-mail cadastrado e permanecerá acessível no painel da CONTRATANTE.

---

### ANEXO I — PLANO CONTRATADO

| Campo | Valor |
|---|---|
| Razão social da CONTRATANTE | `{{ razao_social }}` |
| CNPJ / CPF | `{{ documento }}` |
| Representante legal | `{{ responsavel_nome }}` |
| E-mail de faturamento | `{{ email_contato }}` |
| Plano | `{{ plano.nome }}` |
| Valor mensal | R$ `{{ plano.preco_mensal }}` |
| Trial | `{{ plano.trial_dias }}` dias |
| Limite de operadores | `{{ plano.limite_operadores }}` |
| Limite de clientes | `{{ plano.limite_clientes }}` (0 = ilimitado) |
| Data de aceite | gravada em `AceiteDocumentoPlataforma.aceito_em` |
| Hash documento | `AceiteDocumentoPlataforma.hash_documento` |

---

### DECISÕES PENDENTES DO DONO DO NEGÓCIO

1. **Foro de eleição** — cláusula 13.4 (sugestão: comarca de domicílio da NC Fly).
2. **Multa rescisória imotivada** — cláusula 3.3 (sugestão: 30%).
3. **Cap de responsabilidade** — cláusula 6.3 (sugestão: 12 mensalidades).
4. **SLA formal** — cláusula 5 (confirmar 99,5% ou ajustar conforme
   capacidade real da infraestrutura Railway).
5. **Arbitragem sim/não** — cláusula 13.5.
6. **Lista de suboperadores fixos** — cláusula 7.3 (alinhar com arquitetura
   atual: Railway + Resend + gateway + Cloudflare).
