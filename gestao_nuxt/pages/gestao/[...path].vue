<script setup lang="ts">
import { useRoute } from 'vue-router';

const route = useRoute();
</script>

<template>
  <section class="surface-card">
    <h2>Gestão</h2>
    <p>Rota: {{ route.fullPath }}</p>
  </section>
</template>
