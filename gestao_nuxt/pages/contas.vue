<script setup lang="ts">
definePageMeta({
  title: 'Contas',
  subtitle: 'Gerencie contas fidelidade e limites operacionais.',
});

type ContaItem = {
  id: number;
  conta: string;
  responsavel: string;
  limite: number;
  status: string;
};

type ContasResponse = {
  resultados: ContaItem[];
};

const { data, pending, error } = await useFetch<ContasResponse>('/contas', {
  baseURL: '/adm/api',
  credentials: 'include',
});

const formatNumber = (value: number) =>
  new Intl.NumberFormat('pt-BR').format(value ?? 0);
</script>

<template>
  <section class="content-stack">
    <section v-if="error" class="surface-card">
      <p>Não foi possível carregar as contas.</p>
    </section>

    <section v-else class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Contas cadastradas</h3>
          <p class="section-subtitle">Controle de limites, responsáveis e status.</p>
        </div>
        <button class="btn" type="button">Nova conta</button>
      </div>
      <div v-if="pending" class="muted">Carregando...</div>
      <table class="table">
        <thead>
          <tr>
            <th>Conta</th>
            <th>Responsável</th>
            <th>Limite</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="conta in data?.resultados ?? []" :key="conta.id">
            <td>{{ conta.conta }}</td>
            <td>{{ conta.responsavel }}</td>
            <td>{{ formatNumber(conta.limite) }}</td>
            <td><span class="status">{{ conta.status }}</span></td>
          </tr>
          <tr v-if="(data?.resultados ?? []).length === 0 && !pending">
            <td colspan="4" class="muted">Nenhuma conta encontrada.</td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
