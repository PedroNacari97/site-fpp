<script setup lang="ts">
definePageMeta({
  title: 'Clientes',
  subtitle: 'Gestão de contas corporativas e individuais.',
});

type ClienteItem = {
  id: number;
  nome: string;
  segmento: string;
  status: string;
  carteira: number;
};

type ClientesResponse = {
  resultados: ClienteItem[];
};

const { data, pending, error } = await useFetch<ClientesResponse>('/clientes', {
  baseURL: '/adm/api',
  credentials: 'include',
});

const formatNumber = (value: number) =>
  new Intl.NumberFormat('pt-BR').format(value ?? 0);

const formatCarteira = (value: number) => `${formatNumber(value)} pts`;
</script>

<template>
  <section class="content-stack">
    <section v-if="error" class="surface-card">
      <p>Não foi possível carregar os clientes.</p>
    </section>

    <section v-else class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Base de clientes</h3>
          <p class="section-subtitle">Panorama das contas e do status de relacionamento.</p>
        </div>
        <button class="btn btn--outline" type="button">Adicionar cliente</button>
      </div>
      <div v-if="pending" class="muted">Carregando...</div>
      <table class="table">
        <thead>
          <tr>
            <th>Cliente</th>
            <th>Segmento</th>
            <th>Status</th>
            <th>Carteira</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="cliente in data?.resultados ?? []" :key="cliente.id">
            <td>{{ cliente.nome }}</td>
            <td>{{ cliente.segmento }}</td>
            <td><span class="status">{{ cliente.status }}</span></td>
            <td>{{ formatCarteira(cliente.carteira) }}</td>
          </tr>
          <tr v-if="(data?.resultados ?? []).length === 0 && !pending">
            <td colspan="4" class="muted">Nenhum cliente encontrado.</td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
