<script setup lang="ts">
definePageMeta({
  title: 'Cards e Resumos',
  subtitle: 'Indicadores estratégicos com foco em performance e uso de pontos.',
});

const cards = [
  { title: 'Saldo médio por cliente', value: '24.860 pts', detail: 'Base ativa' },
  { title: 'Emissões expressas', value: '38%', detail: 'Últimos 30 dias' },
  { title: 'Taxa de aprovação', value: '92%', detail: 'Equipe de emissões' },
  { title: 'Top programa', value: 'Smiles', detail: '45% das emissões' },
];

const summaries = [
  { label: 'Tickets abertos', value: '12' },
  { label: 'Solicitações urgentes', value: '3' },
  { label: 'Clientes inativos', value: '14' },
];
</script>

<template>
  <section class="content-stack">
    <div class="stats-grid">
      <article v-for="card in cards" :key="card.title" class="stat-card">
        <p class="stat-label">{{ card.title }}</p>
        <div class="stat-value">
          <span>{{ card.value }}</span>
          <span class="stat-trend">{{ card.detail }}</span>
        </div>
      </article>
    </div>

    <section class="surface-card">
      <h3 class="section-title">Resumo operacional</h3>
      <div class="summary-grid">
        <div v-for="summary in summaries" :key="summary.label" class="summary-card">
          <span class="summary-label">{{ summary.label }}</span>
          <strong class="summary-value">{{ summary.value }}</strong>
        </div>
      </div>
    </section>
  </section>
</template>
