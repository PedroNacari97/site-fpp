import pandas as pd
from django.core.management.base import BaseCommand
from gestao.models import Aeroporto

class Command(BaseCommand):
    help = 'Importa aeroportos a partir de um arquivo Excel com colunas: Cidade e Código IATA'

    def add_arguments(self, parser):
        parser.add_argument('arquivo', type=str, help='Caminho para o arquivo Excel com os aeroportos')

    def handle(self, *args, **kwargs):
        caminho_arquivo = kwargs['arquivo']
        df = pd.read_excel(caminho_arquivo)

        total = 0
        for _, row in df.iterrows():
            nome = row['Cidade']
            sigla = row['Código IATA']

            if pd.notna(nome) and pd.notna(sigla):
                aeroporto, created = Aeroporto.objects.get_or_create(
                    sigla=sigla.strip().upper(),
                    defaults={'nome': nome.strip()}
                )
                if created:
                    total += 1

        self.stdout.write(self.style.SUCCESS(f'{total} aeroportos importados com sucesso!'))
