<script setup lang="ts">
definePageMeta({
  title: 'Contas',
  subtitle: 'Gerencie contas fidelidade e limites operacionais.',
});

const contas = [
  { conta: 'Smiles Corporativo', responsavel: 'Equipe A', limite: '500.000 pts', status: 'Ativa' },
  { conta: 'TudoAzul Prime', responsavel: 'Equipe B', limite: '240.000 pts', status: 'Ativa' },
  { conta: 'LATAM Pass Gold', responsavel: 'Equipe C', limite: '320.000 pts', status: 'Revisão' },
];
</script>

<template>
  <section class="content-stack">
    <section class="surface-card">
      <div class="table-header">
        <div>
          <h3 class="section-title">Contas cadastradas</h3>
          <p class="section-subtitle">Controle de limites, responsáveis e status.</p>
        </div>
        <button class="btn" type="button">Nova conta</button>
      </div>
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
          <tr v-for="conta in contas" :key="conta.conta">
            <td>{{ conta.conta }}</td>
            <td>{{ conta.responsavel }}</td>
            <td>{{ conta.limite }}</td>
            <td><span class="status">{{ conta.status }}</span></td>
          </tr>
        </tbody>
      </table>
    </section>
  </section>
</template>
