<script setup lang="ts">
definePageMeta({
  title: 'Clientes',
  subtitle: 'Gestão de contas corporativas e individuais.',
});

const clientes = [
  { nome: 'Grupo Trix', segmento: 'Corporativo', status: 'Ativo', carteira: '820.000 pts' },
  { nome: 'Marina Duarte', segmento: 'Individual', status: 'Ativo', carteira: '54.300 pts' },
  { nome: 'Agência Horizonte', segmento: 'Corporativo', status: 'Em revisão', carteira: '210.900 pts' },
  { nome: 'Lucas Peres', segmento: 'Individual', status: 'Inativo', carteira: '12.000 pts' },
];
</script>

<template>
  <section class="content-stack">
    <section class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Base de clientes</h3>
          <p class="section-subtitle">Panorama das contas e do status de relacionamento.</p>
        </div>
        <button class="btn btn--outline" type="button">Adicionar cliente</button>
      </div>
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
          <tr v-for="cliente in clientes" :key="cliente.nome">
            <td>{{ cliente.nome }}</td>
            <td>{{ cliente.segmento }}</td>
            <td><span class="status">{{ cliente.status }}</span></td>
            <td>{{ cliente.carteira }}</td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
