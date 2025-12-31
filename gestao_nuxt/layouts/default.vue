<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useHead } from '#imports';

type NavItem = {
  label: string;
  to: string;
  icon: string;
};

const route = useRoute();
const isSidebarOpen = ref(false);
let stopSidebarWatch: (() => void) | null = null;

const iconDashboard = `
  <path d="M3 12 12 3l9 9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M9 21V9h6v12" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconCards = `
  <path d="M4 7h16v10H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M4 10h16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconDoc = `
  <path d="M4 4h16v16H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M7 7h10M7 11h10M7 15h6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconUsers = `
  <path d="M16 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <circle cx="8.5" cy="7" r="4" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M20 8v6M23 11h-6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconCalendar = `
  <path d="M4 4h16v16H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M8 2v4M16 2v4M4 10h16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconGrid = `
  <path d="M4 4h16v6H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M4 14h10v6H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M18 14v6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/', icon: iconDashboard },
  { label: 'Cards e Resumos', to: '/cards', icon: iconCards },
  { label: 'Emissões', to: '/emissoes', icon: iconDoc },
  { label: 'Clientes', to: '/clientes', icon: iconUsers },
  { label: 'Contas', to: '/contas', icon: iconCalendar },
  { label: 'Programas', to: '/programas', icon: iconGrid },
];

const pageTitle = computed(() => route.meta?.title ?? 'Gestão');
const pageSubtitle = computed(() => route.meta?.subtitle ?? '');

const isActive = (path: string) => route.path === path;

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const closeSidebar = () => {
  isSidebarOpen.value = false;
};

useHead(() => ({
  title: pageTitle.value,
}));

onMounted(() => {
  stopSidebarWatch = watch(
    isSidebarOpen,
    (value) => {
      document.body.classList.toggle('sidebar-open', value);
    },
    { immediate: true },
  );
});

onBeforeUnmount(() => {
  stopSidebarWatch?.();
  document.body.classList.remove('sidebar-open');
});
</script>

<template>
  <div class="app-shell">
    <div class="sidebar-overlay" data-sidebar-overlay @click="closeSidebar"></div>

    <aside class="sidebar" data-sidebar>
      <div class="sidebar-header">
        <h1 class="sidebar-title">NCfly</h1>
        <button class="icon-button sidebar-close" type="button" aria-label="Fechar menu" @click="closeSidebar">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
            <path
              d="M6 6l12 12M18 6l-12 12"
              fill="none"
              stroke="currentColor"
              stroke-linecap="round"
              stroke-linejoin="round"
              stroke-width="2"
            />
          </svg>
        </button>
      </div>

      <nav class="sidebar-nav">
        <template v-for="item in navItems" :key="item.to">
          <NuxtLink class="nav-item" :class="{ 'is-active': isActive(item.to) }" :to="item.to">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" v-html="item.icon"></svg>
            <span>{{ item.label }}</span>
          </NuxtLink>
        </template>
      </nav>
    </aside>

    <div class="app-shell__content">
      <header class="app-header">
        <div class="app-header__left">
          <button class="icon-button menu-button" type="button" aria-label="Abrir menu" @click="toggleSidebar">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true">
              <path
                d="M4 6h16M4 12h16M4 18h16"
                fill="none"
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
              />
            </svg>
          </button>
          <h2 class="app-header__title">Gestão</h2>
        </div>
        <div class="app-header__actions">
          <span class="user-name">Ana Carolina</span>
          <button class="icon-button" type="button" aria-label="Alternar modo escuro">🌙</button>
          <NuxtLink class="btn btn--outline btn--sm" to="/logout">Logout</NuxtLink>
        </div>
      </header>

      <main class="app-main">
        <div class="page-shell">
          <div class="page-header">
            <div class="page-header__titles">
              <h1 class="page-title">{{ pageTitle }}</h1>
              <p v-if="pageSubtitle" class="page-subtitle">{{ pageSubtitle }}</p>
            </div>
            <div class="page-actions">
              <slot name="page-actions" />
            </div>
          </div>

          <slot name="messages" />
          <slot />
        </div>
      </main>
    </div>
  </div>
</template>
