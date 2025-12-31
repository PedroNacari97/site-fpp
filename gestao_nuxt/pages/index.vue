<script setup lang="ts">
definePageMeta({
  title: 'Dashboard',
  subtitle: 'Visão geral das operações e alertas principais.',
});

const summaryCards = [
  { label: 'Emissões do mês', value: '1.284', trend: '+12%' },
  { label: 'Saldo de pontos', value: '8.520.430', trend: '+4%' },
  { label: 'Clientes ativos', value: '342', trend: '+18%' },
  { label: 'Alertas críticos', value: '5', trend: '-2' },
];

const pendingActions = [
  {
    title: 'Revisar emissão #4281',
    description: 'Solicitação aguardando aprovação do supervisor.',
    status: 'Aguardando',
  },
  {
    title: 'Atualizar tarifas LATAM',
    description: 'Tabela expira hoje às 18h.',
    status: 'Urgente',
  },
  {
    title: 'Confirmar renovação do cliente VipClub',
    description: 'Contrato vence em 7 dias.',
    status: 'Em análise',
  },
];

const latestEmissoes = [
  { cliente: 'Marina Duarte', programa: 'Smiles', pontos: '86.000', status: 'Emitido' },
  { cliente: 'João Henrique', programa: 'TudoAzul', pontos: '32.500', status: 'Pendente' },
  { cliente: 'Grupo Vitta', programa: 'LATAM Pass', pontos: '140.200', status: 'Emitido' },
];
</script>

<template>
  <section class="content-stack">
    <div class="stats-grid">
      <article v-for="card in summaryCards" :key="card.label" class="stat-card">
        <p class="stat-label">{{ card.label }}</p>
        <div class="stat-value">
          <span>{{ card.value }}</span>
          <span class="stat-trend">{{ card.trend }}</span>
        </div>
      </article>
    </div>

    <div class="data-grid">
      <section class="surface-card">
        <h3 class="section-title">Ações pendentes</h3>
        <div class="list-stack">
          <article v-for="item in pendingActions" :key="item.title" class="list-item">
            <div>
              <h4>{{ item.title }}</h4>
              <p>{{ item.description }}</p>
            </div>
            <span class="pill">{{ item.status }}</span>
          </article>
        </div>
      </section>

      <section class="surface-card">
        <h3 class="section-title">Últimas emissões</h3>
        <table class="table">
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Programa</th>
              <th>Pontos</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in latestEmissoes" :key="row.cliente">
              <td>{{ row.cliente }}</td>
              <td>{{ row.programa }}</td>
              <td>{{ row.pontos }}</td>
              <td><span class="status">{{ row.status }}</span></td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>
  </section>
</template>
