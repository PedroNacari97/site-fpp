<script setup lang="ts">
definePageMeta({
  title: 'Emissões',
  subtitle: 'Acompanhe as solicitações e o fluxo de aprovação.',
});

const emissoes = [
  {
    id: '#8421',
    cliente: 'Estúdio Laguna',
    programa: 'LATAM Pass',
    pontos: '120.000',
    status: 'Aprovado',
  },
  {
    id: '#8420',
    cliente: 'Paulo Cardoso',
    programa: 'Smiles',
    pontos: '54.200',
    status: 'Em análise',
  },
  {
    id: '#8419',
    cliente: 'Clínica Orbit',
    programa: 'TudoAzul',
    pontos: '78.900',
    status: 'Pendente',
  },
  {
    id: '#8418',
    cliente: 'Grupo Lume',
    programa: 'Smiles',
    pontos: '95.400',
    status: 'Aprovado',
  },
];
</script>

<template>
  <section class="content-stack">
    <section class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Solicitações recentes</h3>
          <p class="section-subtitle">Últimas movimentações cadastradas pelos operadores.</p>
        </div>
        <button class="btn" type="button">Nova emissão</button>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Protocolo</th>
            <th>Cliente</th>
            <th>Programa</th>
            <th>Pontos</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="emissao in emissoes" :key="emissao.id">
            <td>{{ emissao.id }}</td>
            <td>{{ emissao.cliente }}</td>
            <td>{{ emissao.programa }}</td>
            <td>{{ emissao.pontos }}</td>
            <td><span class="status">{{ emissao.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
