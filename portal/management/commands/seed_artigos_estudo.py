"""Popula modulos e artigos educativos com conteudo de demonstracao."""
from django.core.management.base import BaseCommand
from django.utils import timezone


MODULOS = [
    {"titulo": "Fundamentos de Milhas", "descricao": "Aprenda o basico sobre programas de fidelidade e como acumular milhas aereas.", "icone": "&#9992;", "cor": "#2563eb", "ordem": 1},
    {"titulo": "Estrategias de Acumulo", "descricao": "Tecnicas avancadas para maximizar o acumulo de milhas em compras do dia a dia.", "icone": "&#128200;", "cor": "#059669", "ordem": 2},
    {"titulo": "Emissao de Passagens", "descricao": "Como encontrar e emitir passagens aereas usando milhas de forma inteligente.", "icone": "&#127907;", "cor": "#d97706", "ordem": 3},
    {"titulo": "Cartoes de Credito", "descricao": "Guia completo sobre os melhores cartoes para acumular milhas no Brasil.", "icone": "&#128179;", "cor": "#7c3aed", "ordem": 4},
    {"titulo": "Programas de Fidelidade", "descricao": "Comparativo entre Smiles, Latam Pass, TudoAzul e programas internacionais.", "icone": "&#11088;", "cor": "#dc2626", "ordem": 5},
    {"titulo": "Viagens Internacionais", "descricao": "Dicas para planejar viagens internacionais com milhas e pontos.", "icone": "&#127758;", "cor": "#0891b2", "ordem": 6},
]

ARTIGOS = [
    {
        "modulo_idx": 0, "titulo": "O que sao milhas aereas e como funcionam",
        "resumo": "Entenda o conceito de milhas aereas, como os programas de fidelidade operam e por que milhas se tornaram uma moeda valiosa.",
        "conteudo": "<h2>Introducao ao mundo das milhas</h2><p>Milhas aereas sao pontos acumulados em programas de fidelidade de companhias aereas. Cada programa tem suas regras, mas o principio e simples: voce acumula pontos e troca por passagens ou upgrades.</p><h2>Como funcionam os programas</h2><p>Os principais programas no Brasil sao Smiles (GOL), Latam Pass (LATAM) e TudoAzul (Azul). Cada um tem tabelas de resgate, categorias de assento e regras de acumulo proprias.</p><h3>Acumulo por voo</h3><p>Ao voar, voce acumula milhas proporcionais a distancia e classe do bilhete. Voos mais longos e classes executivas rendem mais milhas.</p><h3>Acumulo por parceiros</h3><p>Alem de voar, voce pode acumular milhas com cartoes de credito, compras em lojas parceiras e transferencias de pontos bancarios.</p><h2>Por que milhas tem valor</h2><p>Uma milha pode valer de R$ 0,01 a R$ 0,15 dependendo do resgate. Saber escolher o momento certo para resgatar e o que separa um usuario casual de um mileiro estrategico.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 7, "ordem": 1, "status": "published",
    },
    {
        "modulo_idx": 0, "titulo": "Glossario completo do mercado de milhas",
        "resumo": "Todos os termos que voce precisa conhecer: CPM, stopover, OW, RT, sweetspot e muito mais.",
        "conteudo": "<h2>Termos essenciais</h2><p>O mercado de milhas tem seu proprio vocabulario. Conhecer esses termos e fundamental para aproveitar as melhores oportunidades.</p><h2>CPM — Custo por milha</h2><p>O CPM e a metrica mais importante. Ele indica quanto voce paga por cada milha. Quanto menor o CPM, melhor a compra.</p><h2>Stopover e conexao</h2><p>Stopover e quando voce para em uma cidade intermediaria por mais de 24h. Alguns programas permitem stopover gratuito, o que equivale a duas viagens pelo preco de uma.</p><h2>OW e RT</h2><p>OW (one-way) e ida simples. RT (round-trip) e ida e volta. Nem sempre o RT custa o dobro do OW — fique atento.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 5, "ordem": 2, "status": "published",
    },
    {
        "modulo_idx": 1, "titulo": "Como acumular milhas sem voar",
        "resumo": "Descubra as principais formas de acumular milhas no dia a dia usando cartoes de credito, shopping de milhas e transferencias.",
        "conteudo": "<h2>Acumulo terrestre</h2><p>Voce nao precisa voar para acumular milhas. Na verdade, a maioria dos mileiros profissionais acumula mais milhas no chao do que no ar.</p><h2>Cartoes de credito</h2><p>A principal fonte de acumulo e o cartao de credito. Cartoes premium podem render ate 3 pontos por dolar gasto, que depois sao transferidos para programas aereos.</p><h2>Shopping de milhas</h2><p>Portais como Smiles Shopping e Livelo permitem ganhar milhas extras em compras online em lojas como Amazon, Magazine Luiza e Netshoes.</p><h2>Transferencias bonificadas</h2><p>Periodicamente, os programas oferecem bonus de 50% a 100% nas transferencias de pontos bancarios. Esses momentos sao os melhores para converter pontos em milhas.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 8, "ordem": 1, "status": "published",
    },
    {
        "modulo_idx": 2, "titulo": "Como encontrar emissoes com bom custo-beneficio",
        "resumo": "Aprenda a usar ferramentas de busca, alertas e tecnicas para encontrar os melhores resgates.",
        "conteudo": "<h2>Ferramentas de busca</h2><p>Sites como Google Flights, Skyscanner e os proprios buscadores dos programas de fidelidade sao essenciais para encontrar voos com disponibilidade de milhas.</p><h2>Flexibilidade e chave</h2><p>Quanto mais flexivel voce for nas datas e destinos, melhores serao os resgates. Viajar fora da alta temporada pode reduzir o custo em milhas pela metade.</p><h2>Alertas de oportunidades</h2><p>Servicos como o NC Fly enviam alertas quando surgem oportunidades excepcionais de resgate. Ficar atento a esses alertas pode fazer voce economizar milhares de milhas.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 6, "ordem": 1, "status": "published",
    },
    {
        "modulo_idx": 3, "titulo": "Top 5 cartoes para acumular milhas em 2025",
        "resumo": "Comparativo detalhado dos melhores cartoes de credito para quem quer maximizar o acumulo de milhas aereas.",
        "conteudo": "<h2>Criterios de avaliacao</h2><p>Avaliamos os cartoes com base em: taxa de acumulo, anuidade, beneficios extras, flexibilidade de transferencia e custo-beneficio geral.</p><h2>1. Cartao Premium A</h2><p>Taxa de 3 pontos por dolar, acesso a salas VIP e transferencia para 15 programas aereos. Anuidade elevada mas compensada pelos beneficios.</p><h2>2. Cartao Intermediario B</h2><p>2 pontos por dolar com anuidade acessivel. Otima opcao para quem gasta entre R$ 3.000 e R$ 8.000 por mes.</p><h2>Conclusao</h2><p>O melhor cartao depende do seu perfil de gastos. Faca as contas considerando sua media mensal e os programas que voce mais usa.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 10, "ordem": 1, "status": "published",
    },
    {
        "modulo_idx": 4, "titulo": "Smiles vs Latam Pass: qual programa escolher",
        "resumo": "Analise comparativa entre os dois maiores programas de fidelidade do Brasil.",
        "conteudo": "<h2>Visao geral</h2><p>Smiles (GOL) e Latam Pass (LATAM) sao os dois gigantes do mercado brasileiro. Cada um tem vantagens e desvantagens que voce precisa conhecer.</p><h2>Rede de destinos</h2><p>A LATAM tem vantagem em voos internacionais, especialmente para Europa e America do Sul. A GOL, via Smiles, compensa com parcerias internacionais via SkyTeam.</p><h2>Tabela de resgate</h2><p>As tabelas mudam frequentemente. Em geral, voos domesticos sao mais baratos no Smiles, enquanto voos internacionais em executiva podem ser melhores no Latam Pass.</p><h2>Qual escolher?</h2><p>A resposta e: os dois! Diversificar entre programas permite aproveitar as melhores oportunidades de cada um.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 8, "ordem": 1, "status": "published",
    },
    {
        "modulo_idx": 5, "titulo": "Como planejar uma viagem internacional com milhas",
        "resumo": "Passo a passo para planejar sua proxima viagem internacional usando milhas de forma estrategica.",
        "conteudo": "<h2>Planejamento antecipado</h2><p>Viagens internacionais com milhas exigem planejamento de 6 a 12 meses de antecedencia, especialmente para classes executiva e primeira classe.</p><h2>Escolha do programa</h2><p>Identifique qual programa oferece o melhor resgate para seu destino. Use ferramentas como AwardHacker para comparar custos entre programas.</p><h2>Acumulo direcionado</h2><p>Uma vez definido o programa, concentre seu acumulo nele. Transferencias bonificadas podem acelerar bastante esse processo.</p><h2>Dicas extras</h2><p>Considere stopover para conhecer uma cidade extra sem custo adicional de milhas. Alguns programas como o ANA Mileage Club sao famosos por permitir rotas criativas.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 9, "ordem": 1, "status": "published",
    },
    {
        "modulo_idx": 1, "titulo": "Transferencias bonificadas: quando e como aproveitar",
        "resumo": "Entenda como funcionam as promocoes de transferencia de pontos bancarios para programas de milhas.",
        "conteudo": "<h2>O que sao transferencias bonificadas</h2><p>Sao promocoes onde os programas oferecem bonus ao transferir pontos de cartoes ou bancos. Um bonus de 100% significa que para cada 1.000 pontos transferidos, voce recebe 2.000 milhas.</p><h2>Quando acontecem</h2><p>As melhores promocoes costumam aparecer em datas como Black Friday, inicio de temporada e periodos de baixa demanda dos programas.</p><h2>Como se preparar</h2><p>Mantenha pontos acumulados nos bancos e esteja pronto para transferir quando surgir uma boa bonificacao. Assine alertas de promocoes para nao perder nenhuma oportunidade.</p>",
        "autor": "Redacao NC Fly", "tempo_leitura": 6, "ordem": 2, "status": "published",
    },
]


class Command(BaseCommand):
    help = "Popula modulos e artigos educativos com conteudo de demonstracao"

    def handle(self, *args, **options):
        from django.template.defaultfilters import slugify
        from portal.models import ModuloEstudo, ArtigoEstudo

        modulos_objs = []
        for m in MODULOS:
            slug = slugify(m["titulo"])
            obj, created = ModuloEstudo.objects.update_or_create(
                slug=slug,
                defaults={
                    "titulo": m["titulo"],
                    "descricao": m["descricao"],
                    "icone": m["icone"],
                    "cor": m["cor"],
                    "ordem": m["ordem"],
                    "ativo": True,
                },
            )
            modulos_objs.append(obj)
            self.stdout.write(f"{'Criado' if created else 'Atualizado'} modulo: {obj.titulo}")

        for a in ARTIGOS:
            modulo = modulos_objs[a["modulo_idx"]]
            slug = slugify(a["titulo"])
            defaults = {
                "titulo": a["titulo"],
                "resumo": a["resumo"],
                "conteudo": a["conteudo"],
                "autor": a["autor"],
                "tempo_leitura": a["tempo_leitura"],
                "ordem": a["ordem"],
                "status": a["status"],
                "modulo": modulo,
            }
            if a["status"] == "published":
                defaults["publicado_em"] = timezone.now()
            obj, created = ArtigoEstudo.objects.update_or_create(
                slug=slug,
                defaults=defaults,
            )
            self.stdout.write(f"{'Criado' if created else 'Atualizado'} artigo: {obj.titulo}")

        self.stdout.write(self.style.SUCCESS(f"Seed concluido: {len(modulos_objs)} modulos, {len(ARTIGOS)} artigos"))
