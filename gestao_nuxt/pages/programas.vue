<script setup lang="ts">
definePageMeta({
  title: 'Programas',
  subtitle: 'Catálogo de programas de fidelidade integrados.',
});

const programas = [
  { nome: 'Smiles', parceiros: 'Gol, Qatar, Air France', status: 'Ativo' },
  { nome: 'LATAM Pass', parceiros: 'LATAM, Delta, Iberia', status: 'Ativo' },
  { nome: 'TudoAzul', parceiros: 'Azul, United, Copa', status: 'Em atualização' },
];
</script>

<template>
  <section class="content-stack">
    <section class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Programas cadastrados</h3>
          <p class="section-subtitle">Status e parceiros principais de cada programa.</p>
        </div>
        <button class="btn btn--outline" type="button">Adicionar programa</button>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>Programa</th>
            <th>Parceiros</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="programa in programas" :key="programa.nome">
            <td>{{ programa.nome }}</td>
            <td>{{ programa.parceiros }}</td>
            <td><span class="status">{{ programa.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
