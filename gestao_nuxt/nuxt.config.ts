export default defineNuxtConfig({
  css: ['~/assets/css/gestao.css'],
  app: {
    head: {
      titleTemplate: (titleChunk) =>
        titleChunk ? `${titleChunk} - Gestão de Pontos` : 'Gestão de Pontos',
    },
  },
});
