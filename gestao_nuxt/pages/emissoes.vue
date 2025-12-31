<script setup lang="ts">
import { ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';

definePageMeta({
  title: 'Emissões',
  subtitle: 'Listagem completa das emissões cadastradas.',
});

type SelectOption = {
  id: number;
  nome: string;
};

type EmissaoItem = {
  id: number;
  cliente: string;
  programa: string;
  aeroporto_partida: string | null;
  aeroporto_destino: string | null;
  data_ida: string | null;
  data_volta: string | null;
  qtd_passageiros: number;
  valor_referencia: number;
  valor_taxas: number;
  pontos_utilizados: number;
  economia_obtida: number;
  detalhes: string | null;
};

type EmissaoResponse = {
  resultados: EmissaoItem[];
  programas: SelectOption[];
  clientes: SelectOption[];
};

const route = useRoute();
const router = useRouter();

const filters = ref({
  programa: (route.query.programa as string) ?? '',
  cliente: (route.query.cliente as string) ?? '',
  q: (route.query.q as string) ?? '',
  data_ini: (route.query.data_ini as string) ?? '',
  data_fim: (route.query.data_fim as string) ?? '',
});

const { data, pending, error } = await useFetch<EmissaoResponse>('/emissoes', {
  baseURL: '/adm/api',
  credentials: 'include',
  query: route.query,
});

watch(
  () => route.query,
  (query) => {
    filters.value = {
      programa: (query.programa as string) ?? '',
      cliente: (query.cliente as string) ?? '',
      q: (query.q as string) ?? '',
      data_ini: (query.data_ini as string) ?? '',
      data_fim: (query.data_fim as string) ?? '',
    };
  },
);

const formatDate = (value: string | null) => {
  if (!value) return '—';
  return new Intl.DateTimeFormat('pt-BR').format(new Date(value));
};

const formatCurrency = (value: number) =>
  new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' }).format(
    value ?? 0,
  );

const formatNumber = (value: number) =>
  new Intl.NumberFormat('pt-BR').format(value ?? 0);

const applyFilters = () => {
  const query: Record<string, string> = {};
  if (filters.value.programa) query.programa = filters.value.programa;
  if (filters.value.cliente) query.cliente = filters.value.cliente;
  if (filters.value.q) query.q = filters.value.q;
  if (filters.value.data_ini) query.data_ini = filters.value.data_ini;
  if (filters.value.data_fim) query.data_fim = filters.value.data_fim;
  router.push({ query });
};
</script>

<template>
  <section class="stacked">
    <section class="surface-card filter-panel">
      <form class="filter-body" @submit.prevent="applyFilters">
        <div class="form-grid">
          <label class="form-field">
            <span class="form-label">Programa</span>
            <select v-model="filters.programa">
              <option value="">Todos</option>
              <option v-for="programa in data?.programas ?? []" :key="programa.id" :value="programa.id">
                {{ programa.nome }}
              </option>
            </select>
          </label>
          <label class="form-field">
            <span class="form-label">Cliente</span>
            <select v-model="filters.cliente">
              <option value="">Todos</option>
              <option v-for="cliente in data?.clientes ?? []" :key="cliente.id" :value="cliente.id">
                {{ cliente.nome }}
              </option>
            </select>
          </label>
          <label class="form-field">
            <span class="form-label">Busca</span>
            <input v-model="filters.q" type="text" placeholder="Aeroporto ou usuário" />
          </label>
          <label class="form-field">
            <span class="form-label">Data ida (início)</span>
            <input v-model="filters.data_ini" type="date" />
          </label>
          <label class="form-field">
            <span class="form-label">Data volta (fim)</span>
            <input v-model="filters.data_fim" type="date" />
          </label>
        </div>
        <div class="filter-actions">
          <button class="btn btn-primary" type="submit">Aplicar filtros</button>
        </div>
      </form>
    </section>

    <section v-if="error" class="surface-card">
      <p>Não foi possível carregar as emissões.</p>
    </section>

    <section v-else class="surface-card">
      <div class="section-heading">
        <div>
          <p class="eyebrow">Emissões</p>
          <h2 class="section-title">Solicitações</h2>
          <p class="section-subtitle">Listagem filtrada de emissões cadastradas.</p>
        </div>
      </div>

      <div v-if="pending" class="muted">Carregando...</div>

      <div v-else class="table-wrapper">
        <table class="data-table">
          <thead>
            <tr>
              <th>Cliente</th>
              <th>Programa</th>
              <th>Origem</th>
              <th>Destino</th>
              <th>Ida</th>
              <th>Volta</th>
              <th>Passageiros</th>
              <th>Valor referência</th>
              <th>Taxas</th>
              <th>Pontos</th>
              <th>Economia</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="emissao in data?.resultados ?? []" :key="emissao.id">
              <td>{{ emissao.cliente }}</td>
              <td>{{ emissao.programa }}</td>
              <td>{{ emissao.aeroporto_partida ?? '—' }}</td>
              <td>{{ emissao.aeroporto_destino ?? '—' }}</td>
              <td>{{ formatDate(emissao.data_ida) }}</td>
              <td>{{ formatDate(emissao.data_volta) }}</td>
              <td>{{ formatNumber(emissao.qtd_passageiros) }}</td>
              <td>{{ formatCurrency(emissao.valor_referencia) }}</td>
              <td>{{ formatCurrency(emissao.valor_taxas) }}</td>
              <td>{{ formatNumber(emissao.pontos_utilizados) }}</td>
              <td>{{ formatCurrency(emissao.economia_obtida) }}</td>
            </tr>
            <tr v-if="(data?.resultados ?? []).length === 0">
              <td colspan="11" class="muted">Nenhuma emissão encontrada.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </section>
</template>
