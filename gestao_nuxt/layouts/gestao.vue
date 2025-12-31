<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useHead } from '#imports';

type NavItem = {
  label: string;
  to: string;
  icon: string;
};

type NavGroup = {
  label: string;
  icon: string;
  children: NavItem[];
};

const props = withDefaults(
  defineProps<{
    isSuperuser?: boolean;
    profile?: string;
    userName?: string;
    appTitle?: string;
    headerTitle?: string;
  }>(),
  {
    isSuperuser: false,
    profile: 'operador',
    userName: 'Usuário',
    appTitle: 'Gestão Admin',
    headerTitle: 'Painel Administrativo',
  },
);

const route = useRoute();
const isSidebarOpen = ref(false);
let stopSidebarWatch: (() => void) | null = null;

const iconDashboard = `
  <path d="M3 12 12 3l9 9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M9 21V9h6v12" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
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

const iconList = `
  <path d="M3 7h18" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M3 12h18" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M3 17h18" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconPlane = `
  <path d="M2 12h20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M5 12l6-6M5 12l6 6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconDoc = `
  <path d="M4 4h16v16H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M7 7h10M7 11h10M7 15h6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconHotel = `
  <path d="M3 20h18" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M4 20V7a3 3 0 0 1 3-3h10a3 3 0 0 1 3 3v13" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M8 14h.01M12 14h.01M16 14h.01" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconCalculator = `
  <path d="M6 4h12v16H6z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M8 8h8M8 12h2M14 12h2M8 16h2M14 16h2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconGrid = `
  <path d="M4 4h16v6H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M4 14h10v6H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M18 14v6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconPlus = `
  <path d="M4 4h16v16H4z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M8 12h8M12 8v8" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconAirplane = `
  <path d="M2 12h20" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M6 16l6-6 6 6" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconStack = `
  <path d="M2 8l10 4 10-4" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M2 12l10 4 10-4" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconHistory = `
  <path d="M12 6v6l4 2" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconCompany = `
  <path d="M3 10h18v11H3z" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M7 10V3h10v7" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const iconLogout = `
  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M10 17l5-5-5-5" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
  <path d="M15 12H3" fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="2" />
`;

const superuserItems: NavItem[] = [
  {
    label: 'Empresas',
    to: '/gestao/empresas',
    icon: iconCompany,
  },
];

const userItems: NavItem[] = [
  { label: 'Dashboard', to: '/gestao/dashboard', icon: iconDashboard },
  { label: 'Clientes', to: '/gestao/clientes', icon: iconUsers },
  { label: 'Contas Fidelidade', to: '/gestao/contas', icon: iconCalendar },
  { label: 'Contas Administradas', to: '/gestao/contas-administradas', icon: iconList },
  { label: 'Cotações', to: '/gestao/cotacoes', icon: iconPlane },
  { label: 'Emissões', to: '/gestao/emissoes', icon: iconDoc },
  { label: 'Hotéis', to: '/gestao/hoteis', icon: iconHotel },
  { label: 'Calculadora', to: '/gestao/calculadora', icon: iconCalculator },
  { label: 'Emissores Parceiros', to: '/gestao/emissores', icon: iconGrid },
];

const complementares: NavGroup = {
  label: 'Dados Complementares',
  icon: iconPlus,
  children: [
    { label: 'Aeroporto', to: '/gestao/aeroportos', icon: iconAirplane },
    { label: 'Companhia Aérea', to: '/gestao/companhias', icon: iconStack },
    { label: 'Programa de Pontos', to: '/gestao/programas', icon: iconGrid },
  ],
};

const auditoriaItem: NavItem = {
  label: 'Auditoria',
  to: '/gestao/auditoria',
  icon: iconHistory,
};

const adminItems: NavItem[] = [
  { label: 'Usuários Administradores', to: '/gestao/usuarios', icon: iconUsers },
  { label: 'Operadores', to: '/gestao/operadores', icon: iconHistory },
];

const logoutItem: NavItem = {
  label: 'Sair',
  to: '/logout',
  icon: iconLogout,
};

const navItems = computed(() => (props.isSuperuser ? superuserItems : userItems));
const showAdminItems = computed(() => props.isSuperuser || props.profile === 'admin');

const isActive = (path: string) => route.path === path;
const isGroupOpen = (group: NavGroup) => group.children.some((child) => isActive(child.to));

const toggleSidebar = () => {
  isSidebarOpen.value = !isSidebarOpen.value;
};

const closeSidebar = () => {
  isSidebarOpen.value = false;
};

useHead(() => ({
  title: props.headerTitle,
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

        <details v-if="!props.isSuperuser" class="nav-group" :open="isGroupOpen(complementares)">
          <summary class="nav-item nav-item--summary">
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" v-html="complementares.icon"></svg>
            <span>{{ complementares.label }}</span>
          </summary>
          <div class="nav-subitems">
            <NuxtLink
              v-for="child in complementares.children"
              :key="child.to"
              class="nav-item"
              :class="{ 'is-active': isActive(child.to) }"
              :to="child.to"
            >
              <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" v-html="child.icon"></svg>
              <span>{{ child.label }}</span>
            </NuxtLink>
          </div>
        </details>

        <NuxtLink
          v-if="!props.isSuperuser"
          class="nav-item"
          :class="{ 'is-active': isActive(auditoriaItem.to) }"
          :to="auditoriaItem.to"
        >
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" v-html="auditoriaItem.icon"></svg>
          <span>{{ auditoriaItem.label }}</span>
        </NuxtLink>

        <template v-if="showAdminItems">
          <NuxtLink
            v-for="item in adminItems"
            :key="item.to"
            class="nav-item"
            :class="{ 'is-active': isActive(item.to) }"
            :to="item.to"
          >
            <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" v-html="item.icon"></svg>
            <span>{{ item.label }}</span>
          </NuxtLink>
        </template>

        <NuxtLink class="nav-item" :class="{ 'is-active': isActive(logoutItem.to) }" :to="logoutItem.to">
          <svg class="icon" viewBox="0 0 24 24" aria-hidden="true" v-html="logoutItem.icon"></svg>
          <span>{{ logoutItem.label }}</span>
        </NuxtLink>
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
          <h2 class="app-header__title">{{ props.appTitle }}</h2>
        </div>
        <div class="app-header__actions">
          <span class="user-name">{{ props.userName }}</span>
          <button class="icon-button" type="button" aria-label="Alternar modo escuro">🌙</button>
          <slot name="header-actions">
            <NuxtLink class="btn btn--outline btn--sm" to="/logout">Logout</NuxtLink>
          </slot>
        </div>
      </header>

      <main class="app-main">
        <div class="page-shell">
          <div class="page-header">
            <div class="page-header__titles">
              <h1 class="page-title">{{ props.headerTitle }}</h1>
              <slot name="header-subtitle" />
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
