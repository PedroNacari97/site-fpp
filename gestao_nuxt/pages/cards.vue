<script setup lang="ts">
definePageMeta({
  title: 'Cards e Resumos',
  subtitle: 'Indicadores consolidados do painel.',
});

type CardsData = {
  total_titulares: number;
  total_emissoes: number;
  total_pontos: number;
  total_economizado: number;
};

const { data, pending, error } = await useFetch<CardsData>('/cards', {
  baseURL: '/adm/api',
  credentials: 'include',
});

const formatNumber = (value: number) =>
  new Intl.NumberFormat('pt-BR').format(value ?? 0);
const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
    value ?? 0,
  );
</script>

<template>
  <section class="stacked">
    <section v-if="error" class="surface-card">
      <p>Não foi possível carregar os indicadores.</p>
    </section>

    <section v-else-if="pending" class="surface-card">
      <p>Carregando indicadores...</p>
    </section>

    <section v-else class="stat-grid">
      <article class="stat-card">
        <p class="stat-label">Titulares ativos</p>
        <p class="stat-value">{{ formatNumber(data?.total_titulares ?? 0) }}</p>
        <p class="stat-meta">Clientes, contas e parceiros</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Emissões</p>
        <p class="stat-value">{{ formatNumber(data?.total_emissoes ?? 0) }}</p>
        <p class="stat-meta">Total registrado</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Pontos</p>
        <p class="stat-value">{{ formatNumber(data?.total_pontos ?? 0) }}</p>
        <p class="stat-meta">Saldo consolidado</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Economia</p>
        <p class="stat-value">{{ formatCurrency(data?.total_economizado ?? 0) }}</p>
        <p class="stat-meta">Acumulado</p>
      </article>
    </section>
  </section>
</template>
