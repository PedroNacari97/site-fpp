"""
Management command para criar/atualizar os DocumentoPlataforma obrigatorios.

Idempotente — usa update_or_create com `tipo` como lookup.
Pode ser executado multiplas vezes sem duplicar registros.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from gestao.models import DocumentoPlataforma

DOCUMENTOS = [
    {
        "tipo": DocumentoPlataforma.TIPO_TERMOS,
        "defaults": {
            "titulo": "Termos de Uso da Plataforma",
            "conteudo": """<h3>1. Objeto</h3>
<p>Estes Termos de Uso regulam o acesso e uso da plataforma NCfly, um sistema SaaS de gestao para agencias de viagem e profissionais autonomos do setor de turismo.</p>

<h3>2. Cadastro e Acesso</h3>
<p>O usuario declara que as informacoes fornecidas no cadastro sao verdadeiras e se compromete a mante-las atualizadas. O acesso e pessoal e intransferivel.</p>

<h3>3. Uso da Plataforma</h3>
<p>A plataforma deve ser utilizada exclusivamente para fins de gestao de milhas, emissoes de passagens, cotacoes e gerenciamento de clientes da agencia. E proibido:</p>
<ul>
<li>Compartilhar credenciais de acesso com terceiros</li>
<li>Utilizar a plataforma para fins ilegais</li>
<li>Tentar acessar dados de outras empresas cadastradas</li>
<li>Realizar engenharia reversa ou tentativas de acesso nao autorizado</li>
</ul>

<h3>4. Planos e Pagamento</h3>
<p>Os planos sao cobrados mensalmente. O nao pagamento apos o periodo de tolerancia resulta em suspensao do acesso. Todos os planos incluem periodo de trial gratuito.</p>

<h3>5. Cancelamento</h3>
<p>O cancelamento pode ser solicitado a qualquer momento e sera efetivado ao final do periodo ja pago. Nao ha reembolso proporcional.</p>

<h3>6. Disponibilidade</h3>
<p>A NCfly se esforça para manter a plataforma disponivel 24/7, mas nao garante disponibilidade ininterrupta. Manutencoes programadas serao comunicadas com antecedencia.</p>

<h3>7. Propriedade Intelectual</h3>
<p>Todo o conteudo da plataforma, incluindo codigo, design e documentacao, e de propriedade exclusiva da NCfly. Os dados inseridos pelo usuario permanecem de propriedade do usuario.</p>""",
            "versao_atual": "1.0",
            "exige_aceite_empresa": True,
            "ativo": True,
            "observacoes_internas": "",
        },
    },
    {
        "tipo": DocumentoPlataforma.TIPO_PRIVACIDADE,
        "defaults": {
            "titulo": "Politica de Privacidade",
            "conteudo": """<h3>1. Dados Coletados</h3>
<p>Coletamos os seguintes dados pessoais para operacao da plataforma:</p>
<ul>
<li><strong>Dados do responsavel:</strong> nome, CPF, email, telefone</li>
<li><strong>Dados da empresa:</strong> CNPJ, razao social, endereco</li>
<li><strong>Dados de uso:</strong> logs de acesso, acoes realizadas na plataforma</li>
<li><strong>Dados de dispositivo:</strong> IP, navegador, sistema operacional (coletados no aceite)</li>
</ul>

<h3>2. Finalidade do Tratamento</h3>
<p>Os dados sao tratados para:</p>
<ul>
<li>Prestacao do servico contratado (base legal: execucao de contrato)</li>
<li>Comunicacoes sobre a plataforma (base legal: legitimo interesse)</li>
<li>Cumprimento de obrigacoes legais (base legal: obrigacao legal)</li>
</ul>

<h3>3. Compartilhamento</h3>
<p>Seus dados podem ser compartilhados com:</p>
<ul>
<li>Processadores de pagamento (para cobranca)</li>
<li>Servicos de infraestrutura (hospedagem e banco de dados)</li>
</ul>
<p>Nao vendemos nem compartilhamos dados pessoais para fins de marketing de terceiros.</p>

<h3>4. Retencao</h3>
<p>Os dados sao retidos enquanto a conta estiver ativa e por ate 5 anos apos o encerramento, conforme exigencias legais e fiscais.</p>

<h3>5. Direitos do Titular (LGPD)</h3>
<p>Voce pode exercer os seguintes direitos a qualquer momento:</p>
<ul>
<li>Acesso aos seus dados pessoais</li>
<li>Correcao de dados incorretos</li>
<li>Exclusao de dados (direito ao esquecimento)</li>
<li>Portabilidade dos dados</li>
<li>Revogacao de consentimento</li>
</ul>
<p>Para exercer seus direitos, entre em contato pelo email: <strong>privacidade@ncfly.com.br</strong></p>

<h3>6. Seguranca</h3>
<p>Adotamos medidas tecnicas e organizacionais para proteger seus dados, incluindo criptografia em repouso e em transito, controle de acesso e logs de auditoria.</p>""",
            "versao_atual": "1.0",
            "exige_aceite_empresa": True,
            "ativo": True,
            "observacoes_internas": "",
        },
    },
    {
        "tipo": DocumentoPlataforma.TIPO_DPA,
        "defaults": {
            "titulo": "Acordo de Processamento de Dados (DPA)",
            "conteudo": """<h3>1. Definicoes</h3>
<p><strong>Controlador:</strong> a agencia de viagens (empresa contratante).<br>
<strong>Operador:</strong> NCfly (prestador do servico SaaS).<br>
<strong>Dados pessoais:</strong> qualquer informacao relativa a pessoa natural identificada ou identificavel processada na plataforma.</p>

<h3>2. Obrigacoes do Operador (NCfly)</h3>
<ul>
<li>Processar dados pessoais exclusivamente conforme instrucoes do Controlador</li>
<li>Garantir que pessoas autorizadas a tratar dados estejam sujeitas a obrigacao de confidencialidade</li>
<li>Adotar medidas tecnicas e organizacionais de seguranca adequadas</li>
<li>Notificar o Controlador sobre incidentes de seguranca em ate 72 horas</li>
<li>Auxiliar o Controlador no atendimento a solicitacoes de titulares de dados</li>
</ul>

<h3>3. Suboperadores</h3>
<p>O Operador utiliza os seguintes suboperadores:</p>
<ul>
<li>Railway (hospedagem e banco de dados)</li>
<li>Cloudflare (CDN e protecao)</li>
</ul>

<h3>4. Transferencia Internacional</h3>
<p>Caso dados sejam processados fora do Brasil, o Operador garante que os suboperadores adotam nivel adequado de protecao conforme Art. 33 da LGPD.</p>

<h3>5. Retencao e Exclusao</h3>
<p>Ao termino do contrato, o Operador excluira ou devolvera os dados pessoais ao Controlador, conforme solicitado, no prazo de 30 dias.</p>

<h3>6. Auditoria</h3>
<p>O Controlador pode solicitar evidencias de conformidade do Operador, mediante aviso previo de 30 dias.</p>""",
            "versao_atual": "1.0",
            "exige_aceite_empresa": True,
            "ativo": True,
            "observacoes_internas": "",
        },
    },
    {
        "tipo": DocumentoPlataforma.TIPO_SEGURANCA,
        "defaults": {
            "titulo": "Politica de Seguranca e Uso Aceitavel",
            "conteudo": "",
            "versao_atual": "1.0",
            "exige_aceite_empresa": False,
            "ativo": True,
            "observacoes_internas": "",
        },
    },
    {
        "tipo": DocumentoPlataforma.TIPO_CONTRATO_SAAS,
        "defaults": {
            "titulo": "Contrato SaaS B2B",
            "conteudo": "",
            "versao_atual": "1.0",
            "exige_aceite_empresa": False,
            "ativo": True,
            "observacoes_internas": "Contrato de prestacao de servico SaaS para agencias B2B.",
        },
    },
]


class Command(BaseCommand):
    help = "Cria ou atualiza os DocumentoPlataforma obrigatorios (idempotente)."

    def handle(self, *args, **options):
        today = timezone.localdate()
        created_count = 0
        updated_count = 0

        for doc_spec in DOCUMENTOS:
            defaults = doc_spec["defaults"]
            defaults["data_vigencia"] = today

            _obj, created = DocumentoPlataforma.objects.update_or_create(
                tipo=doc_spec["tipo"],
                defaults=defaults,
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Criado: {doc_spec['tipo']}"))
            else:
                updated_count += 1
                self.stdout.write(self.style.SUCCESS(f"  Atualizado: {doc_spec['tipo']}"))

        self.stdout.write(f"\nPronto — {created_count} criado(s), {updated_count} atualizado(s).")
