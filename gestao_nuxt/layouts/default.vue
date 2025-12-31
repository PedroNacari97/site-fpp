<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useHead, useFetch } from '#imports';

type NavItem = {
  label: string;
  to: string;
};

const route = useRoute();
const isSidebarOpen = ref(false);
let stopSidebarWatch: (() => void) | null = null;

const navItems: NavItem[] = [
  { label: 'Dashboard', to: '/' },
  { label: 'Cards e Resumos', to: '/cards' },
  { label: 'Emissões', to: '/emissoes' },
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

const { data: userInfo } = await useFetch<{ name: string }>('/me', {
  baseURL: '/adm/api',
  credentials: 'include',
});

const userName = computed(() => userInfo.value?.name ?? '');

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
  <div class="app-layout">
    <div class="sidebar-overlay" data-sidebar-overlay @click="closeSidebar"></div>

    <aside class="sidebar" data-sidebar>
      <div class="sidebar-header">
        <h1 class="sidebar-title">NCfly</h1>
        <button
          class="icon-button sidebar-close"
          type="button"
          aria-label="Fechar menu"
          data-sidebar-toggle
          @click="closeSidebar"
        >
          ✕
        </button>
      </div>

      <nav class="sidebar-nav">
        <template v-for="item in navItems" :key="item.to">
          <NuxtLink class="nav-item" :class="{ 'is-active': isActive(item.to) }" :to="item.to">
            <span class="sidebar-label">{{ item.label }}</span>
          </NuxtLink>
        </template>
      </nav>
    </aside>

    <main class="content">
      <div class="page-container">
        <header class="topbar">
          <div class="app-header__left">
            <button
              class="icon-button menu-button"
              type="button"
              aria-label="Abrir menu"
              data-sidebar-toggle
              @click="toggleSidebar"
            >
              ☰
            </button>
            <h2>Gestão</h2>
          </div>
          <div class="app-header__actions">
            <span class="user-name">{{ userName }}</span>
            <NuxtLink class="btn btn-secondary" to="/logout">Logout</NuxtLink>
          </div>
        </header>

        <div class="page-shell">
          <div class="page-header">
            <div>
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
      </div>
    </main>
  </div>
</template>
