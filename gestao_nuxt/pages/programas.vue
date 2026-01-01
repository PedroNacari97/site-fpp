<script setup lang="ts">
definePageMeta({
  title: 'Programas',
  subtitle: 'Catálogo de programas de fidelidade integrados.',
});

type ProgramaItem = {
  id: number;
  nome: string;
  parceiros: string;
  status: string;
};

type ProgramasResponse = {
  resultados: ProgramaItem[];
};

const { data, pending, error } = await useFetch<ProgramasResponse>('/programas', {
  baseURL: '/adm/api',
  credentials: 'include',
});
</script>

<template>
  <section class="content-stack">
    <section v-if="error" class="surface-card">
      <p>Não foi possível carregar os programas.</p>
    </section>

    <section v-else class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Programas cadastrados</h3>
          <p class="section-subtitle">Status e parceiros principais de cada programa.</p>
        </div>
        <button class="btn btn--outline" type="button">Adicionar programa</button>
      </div>
      <div v-if="pending" class="muted">Carregando...</div>
      <table class="table">
        <thead>
          <tr>
            <th>Programa</th>
            <th>Parceiros</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="programa in data?.resultados ?? []" :key="programa.id">
            <td>{{ programa.nome }}</td>
            <td>{{ programa.parceiros }}</td>
            <td><span class="status">{{ programa.status }}</span></td>
          </tr>
          <tr v-if="(data?.resultados ?? []).length === 0 && !pending">
            <td colspan="3" class="muted">Nenhum programa encontrado.</td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
