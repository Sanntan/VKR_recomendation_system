<template>
  <div class="status-card" :class="{ healthy: status === 'ok', unhealthy: status === 'error' }">
    <div class="status-dot" />
    <div class="status-text">
      <span class="title">API</span>
      <span class="subtitle">
        {{ statusMessage }}
      </span>
    </div>
    <button class="refresh" type="button" @click="refresh" :disabled="loading">
      Обновить
    </button>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { checkHealth } from "../api/client.js";

const status = ref("unknown");
const loading = ref(false);

const statusMessage = computed(() => {
  if (loading.value) {
    return "Проверка...";
  }
  switch (status.value) {
    case "ok":
      return "Соединение активно";
    case "error":
      return "Нет соединения";
    default:
      return "Статус неизвестен";
  }
});

async function refresh() {
  loading.value = true;
  try {
    const response = await checkHealth();
    status.value = response?.status === "ok" ? "ok" : "error";
  } catch (error) {
    console.error(error);
    status.value = "error";
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  refresh();
});
</script>

<style scoped>
.status-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.75rem 1.25rem;
  border-radius: 0.75rem;
  background-color: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(8px);
  color: inherit;
  border: 1px solid rgba(255, 255, 255, 0.35);
}

.status-card.healthy .status-dot {
  background-color: #4ade80;
  box-shadow: 0 0 12px rgba(74, 222, 128, 0.6);
}

.status-card.unhealthy .status-dot {
  background-color: #f87171;
  box-shadow: 0 0 12px rgba(248, 113, 113, 0.6);
}

.status-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background-color: #facc15;
  transition: background-color 0.3s ease, box-shadow 0.3s ease;
}

.status-text {
  display: flex;
  flex-direction: column;
}

.title {
  font-weight: 600;
  font-size: 0.9rem;
}

.subtitle {
  font-size: 0.8rem;
  opacity: 0.85;
}

.refresh {
  margin-left: auto;
  padding: 0.35rem 0.85rem;
  border-radius: 0.5rem;
  border: none;
  cursor: pointer;
  background-color: rgba(255, 255, 255, 0.15);
  color: inherit;
  transition: background-color 0.2s ease, transform 0.2s ease;
}

.refresh:hover:not(:disabled) {
  background-color: rgba(255, 255, 255, 0.35);
  transform: translateY(-1px);
}

.refresh:disabled {
  opacity: 0.6;
  cursor: default;
}
</style>

