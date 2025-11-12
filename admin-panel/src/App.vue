<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="branding">
        <h1>Админ-панель VKR</h1>
        <p>Базовый интерфейс управления данными проекта</p>
      </div>
      <status-indicator />
    </header>

    <div class="app-body">
      <aside class="sidebar">
        <nav>
          <button
            v-for="item in navigationItems"
            :key="item.id"
            type="button"
            class="nav-item"
            :class="{ active: currentView === item.id }"
            @click="currentView = item.id"
          >
            <span class="nav-title">{{ item.title }}</span>
            <span class="nav-description">{{ item.description }}</span>
          </button>
        </nav>
      </aside>

      <main class="content">
        <component :is="activeComponent" />
      </main>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import StatusIndicator from "./components/StatusIndicator.vue";
import StudentsView from "./components/StudentsView.vue";
import EventsView from "./components/EventsView.vue";
import RecommendationsView from "./components/RecommendationsView.vue";

const navigationItems = [
  {
    id: "students",
    title: "Студенты",
    description: "Поиск по participant_id и карточка студента"
  },
  {
    id: "events",
    title: "Мероприятия",
    description: "Актуальный список мероприятий и состояния"
  },
  {
    id: "recommendations",
    title: "Рекомендации",
    description: "Диагностика работы рекомендаций по студенту"
  }
];

const viewComponents = {
  students: StudentsView,
  events: EventsView,
  recommendations: RecommendationsView
};

const currentView = ref("students");

const activeComponent = computed(() => viewComponents[currentView.value]);
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  color: #111827;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  background: linear-gradient(90deg, #3730a3, #4f46e5);
  color: #ffffff;
  box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);
}

.branding h1 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
}

.branding p {
  margin: 0;
  font-size: 0.95rem;
  opacity: 0.85;
}

.app-body {
  display: grid;
  grid-template-columns: 280px 1fr;
  flex: 1;
  min-height: 0;
}

.sidebar {
  background-color: #ffffff;
  border-right: 1px solid #e5e7eb;
  padding: 1.5rem 1rem;
}

.nav-item {
  display: flex;
  flex-direction: column;
  text-align: left;
  gap: 0.25rem;
  width: 100%;
  padding: 0.75rem 1rem;
  border: 1px solid transparent;
  border-radius: 0.75rem;
  background-color: transparent;
  transition: all 0.2s ease-in-out;
  color: inherit;
}

.nav-item:hover,
.nav-item.active {
  background-color: #eef2ff;
  border-color: #c7d2fe;
  color: #312e81;
}

.nav-title {
  font-weight: 600;
}

.nav-description {
  font-size: 0.85rem;
  color: #6b7280;
}

.content {
  padding: 1.5rem 2rem;
  overflow-y: auto;
}
</style>

