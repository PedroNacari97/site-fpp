<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

definePageMeta({
  title: 'Dashboard',
  subtitle: 'Resumo geral da operação.',
});

type DashboardItem = {
  id: number;
  nome: string;
};

type DashboardData = {
  total_titulares: number;
  total_emissoes: number;
  total_pontos: number;
  total_economizado: number;
  programas: Array<{
    id: number;
    nome: string;
    pontos: number;
    valor_total: number;
    valor_medio: number;
    valor_referencia: number;
  }>;
  emissoes: {
    qtd: number;
    pontos: number;
    valor_referencia: number;
    valor_taxas: number;
    custo_total: number;
    valor_economizado: number;
  };
  hoteis: {
    qtd: number;
    valor_referencia: number;
    valor_pago: number;
    valor_economizado: number;
  };
  clientes: DashboardItem[];
  contas_administradas: DashboardItem[];
  emissores_parceiros: DashboardItem[];
  view_type: string;
};

const route = useRoute();
const router = useRouter();

const { data, pending, error } = await useFetch<DashboardData>('/dashboard', {
  baseURL: '/adm/api',
  credentials: 'include',
  query: route.query,
});

const formatNumber = (value: number) =>
  new Intl.NumberFormat('pt-BR').format(value ?? 0);
const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
    value ?? 0,
  );

const viewType = ref((route.query.view as string) || 'clientes');

const availableTitulares = computed(() => {
  if (viewType.value === 'contas') {
    return data.value?.contas_administradas ?? [];
  }
  if (viewType.value === 'parceiros') {
    return data.value?.emissores_parceiros ?? [];
  }
  return data.value?.clientes ?? [];
});

const selectedEntity = ref(
  viewType.value === 'contas'
    ? (route.query.conta_id as string) ?? ''
    : viewType.value === 'parceiros'
      ? (route.query.emissor_id as string) ?? ''
      : (route.query.cliente_id as string) ?? '',
);

watch(
  () => route.query,
  (query) => {
    viewType.value = (query.view as string) || 'clientes';
    selectedEntity.value =
      viewType.value === 'contas'
        ? (query.conta_id as string) ?? ''
        : viewType.value === 'parceiros'
          ? (query.emissor_id as string) ?? ''
          : (query.cliente_id as string) ?? '';
  },
);

const updateFilters = () => {
  const query: Record<string, string> = {};
  if (viewType.value) {
    query.view = viewType.value;
  }
  if (selectedEntity.value) {
    if (viewType.value === 'contas') {
      query.conta_id = selectedEntity.value;
    } else if (viewType.value === 'parceiros') {
      query.emissor_id = selectedEntity.value;
    } else {
      query.cliente_id = selectedEntity.value;
    }
  }
  router.push({ query });
};
</script>

<template>
  <section class="stacked">
    <section class="surface-card filter-panel" data-filter-panel>
      <form class="filter-body" @submit.prevent="updateFilters">
        <div class="form-grid">
          <label class="form-field">
            <span class="form-label">Tipo de visão</span>
            <select v-model="viewType">
              <option value="clientes">Clientes</option>
              <option value="contas">Contas administradas</option>
              <option value="parceiros">Emissores parceiros</option>
            </select>
          </label>
          <label class="form-field">
            <span class="form-label">Titular</span>
            <select v-model="selectedEntity">
              <option value="">Todos</option>
              <option v-for="item in availableTitulares" :key="item.id" :value="item.id">
                {{ item.nome }}
              </option>
            </select>
          </label>
        </div>
        <div class="filter-actions">
          <button class="btn btn-primary" type="submit">Filtrar</button>
        </div>
      </form>
    </section>

    <section v-if="error" class="surface-card">
      <p>Não foi possível carregar o dashboard.</p>
    </section>

    <section v-else class="stat-grid">
      <article class="stat-card">
        <p class="stat-label">Total de titulares</p>
        <p class="stat-value">{{ formatNumber(data?.total_titulares ?? 0) }}</p>
        <p class="stat-meta">Base ativa</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Emissões</p>
        <p class="stat-value">{{ formatNumber(data?.total_emissoes ?? 0) }}</p>
        <p class="stat-meta">Processadas</p>
      </article>
      <article class="stat-card">
        <p class="stat-label">Pontos</p>
        <p class="stat-value">{{ formatNumber(data?.total_pontos ?? 0) }}</p>
        <p class="stat-meta">Saldo total</p>
      </article>
    </section>

    <section v-if="pending" class="surface-card">
      <p>Carregando indicadores...</p>
    </section>

    <section v-else class="surface-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Resumo financeiro</p>
          <h2 class="section-title">Emissões e hotéis</h2>
          <p class="section-subtitle">Valores consolidados do período.</p>
        </div>
      </div>
      <div class="stat-grid">
        <article class="stat-card">
          <p class="stat-label">Economia total</p>
          <p class="stat-value">{{ formatCurrency(data?.total_economizado ?? 0) }}</p>
          <p class="stat-meta">Somatório de emissões e hotéis</p>
        </article>
        <article class="stat-card">
          <p class="stat-label">Taxas de emissão</p>
          <p class="stat-value">{{ formatCurrency(data?.emissoes.valor_taxas ?? 0) }}</p>
          <p class="stat-meta">Total em taxas</p>
        </article>
        <article class="stat-card">
          <p class="stat-label">Hotéis</p>
          <p class="stat-value">{{ formatNumber(data?.hoteis.qtd ?? 0) }}</p>
          <p class="stat-meta">Reservas cadastradas</p>
        </article>
      </div>
    </section>

    <section v-if="data?.programas?.length" class="surface-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Programas</p>
          <h2 class="section-title">Distribuição de pontos</h2>
        </div>
      </div>
      <div class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Programa</th>
              <th>Pontos</th>
              <th>Valor total</th>
              <th>Valor médio</th>
              <th>Valor referência</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="programa in data?.programas ?? []" :key="programa.id">
              <td>{{ programa.nome }}</td>
              <td>{{ formatNumber(programa.pontos) }}</td>
              <td>{{ formatCurrency(programa.valor_total) }}</td>
              <td>{{ formatCurrency(programa.valor_medio) }}</td>
              <td>{{ formatCurrency(programa.valor_referencia) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
