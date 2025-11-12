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
    <ErrorNotification />
  </div>
</template>

<script setup>
import { computed, ref } from "vue";

import StatusIndicator from "./components/StatusIndicator.vue";
import StudentsView from "./components/StudentsView.vue";
import EventsView from "./components/EventsView.vue";
import RecommendationsView from "./components/RecommendationsView.vue";
import DatabaseToolsView from "./components/DatabaseToolsView.vue";
import ErrorNotification from "./components/ErrorNotification.vue";

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
  },
  {
    id: "maintenance",
    title: "База данных",
    description: "Инструменты загрузки данных и обслуживания"
  }
];

const viewComponents = {
  students: StudentsView,
  events: EventsView,
  recommendations: RecommendationsView,
  maintenance: DatabaseToolsView
};

const currentView = ref("students");

const activeComponent = computed(() => viewComponents[currentView.value]);
</script>

<style scoped>
.app-shell {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  color: #212529;
  background-color: #f8f9fa;
}

.app-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1.5rem 2rem;
  background: #ffffff;
  border-bottom: 1px solid #dee2e6;
  color: #212529;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.branding h1 {
  margin: 0 0 0.25rem 0;
  font-size: 1.75rem;
  color: #212529;
  font-weight: 700;
}

.branding p {
  margin: 0;
  font-size: 0.95rem;
  color: #6c757d;
}

.app-body {
  display: grid;
  grid-template-columns: 280px 1fr;
  flex: 1;
  min-height: 0;
}

.sidebar {
  background-color: #ffffff;
  border-right: 1px solid #dee2e6;
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
  border-radius: 8px;
  background-color: transparent;
  transition: all 0.2s ease-in-out;
  color: #212529;
  margin-bottom: 0.5rem;
}

.nav-item:hover {
  background-color: #f8f9fa;
  border-color: #dee2e6;
}

.nav-item.active {
  background-color: #0d6efd;
  border-color: #0d6efd;
  color: #ffffff;
}

.nav-title {
  font-weight: 600;
}

.nav-description {
  font-size: 0.85rem;
  color: #6c757d;
}

.nav-item.active .nav-description {
  color: rgba(255, 255, 255, 0.85);
}

.content {
  padding: 1.5rem 2rem;
  overflow-y: auto;
}
</style>

