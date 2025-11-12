<template>
  <section class="card">
    <header class="card-header">
      <div>
        <h2>Актуальные мероприятия</h2>
        <p>Данные загружаются из `/events/active`. Можно обновить и изменить лимит записей.</p>
      </div>
      <div class="controls">
        <label>
          <span>Лимит</span>
          <input type="number" v-model.number="limit" min="1" max="200" />
        </label>
        <button type="button" @click="loadEvents" :disabled="loading">
          {{ loading ? "Обновление..." : "Обновить" }}
        </button>
      </div>
    </header>

    <div v-if="error" class="alert error">
      {{ error }}
    </div>

    <p v-if="!loading && !error" class="summary">
      Найдено записей: <strong>{{ events.total }}</strong>
    </p>

    <div v-if="loading" class="loader">
      Загрузка данных...
    </div>

    <div v-else class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Даты</th>
            <th>Формат</th>
            <th>Ссылка</th>
            <th>Лайки</th>
            <th>Дизлайки</th>
            <th>Статус</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in events.events" :key="event.id">
            <td>
              <div class="title">{{ event.title }}</div>
              <div class="description">{{ event.short_description || "—" }}</div>
            </td>
            <td>
              <div>{{ formatDate(event.start_date) }}</div>
              <div>→ {{ formatDate(event.end_date) }}</div>
            </td>
            <td>{{ event.format || "—" }}</td>
            <td>
              <a v-if="event.link" :href="event.link" target="_blank" rel="noopener">Открыть</a>
              <span v-else>—</span>
            </td>
            <td>{{ event.likes_count }}</td>
            <td>{{ event.dislikes_count }}</td>
            <td>
              <span :class="['status-tag', event.is_active ? 'active' : 'inactive']">
                {{ event.is_active ? "Активно" : "Скрыто" }}
              </span>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { onMounted, reactive, ref } from "vue";
import { fetchEvents } from "../api/client.js";

const events = reactive({
  total: 0,
  events: []
});

const limit = ref(20);
const loading = ref(false);
const error = ref("");

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString("ru-RU");
}

async function loadEvents() {
  loading.value = true;
  error.value = "";

  try {
    const response = await fetchEvents({ limit: limit.value });
    events.total = response.total ?? response.events?.length ?? 0;
    events.events = response.events ?? [];
  } catch (err) {
    console.error(err);
    error.value = "Не удалось загрузить данные мероприятий";
    events.total = 0;
    events.events = [];
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  loadEvents();
});
</script>

<style scoped>
.card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.75rem;
  background-color: #ffffff;
  border-radius: 1.25rem;
  border: 1px solid #e5e7eb;
  box-shadow: 0 12px 24px -12px rgba(15, 23, 42, 0.12);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1.5rem;
}

.card-header h2 {
  margin: 0 0 0.35rem;
}

.card-header p {
  margin: 0;
  color: #6b7280;
}

.controls {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.controls label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  color: #4b5563;
}

.controls input {
  width: 80px;
  padding: 0.4rem 0.5rem;
  border-radius: 0.6rem;
  border: 1px solid #d1d5db;
}

button {
  padding: 0.6rem 1.25rem;
  border-radius: 0.75rem;
  border: none;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
}

.alert {
  padding: 0.85rem 1rem;
  border-radius: 0.75rem;
}

.alert.error {
  background-color: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
}

.summary {
  margin: 0;
  color: #4b5563;
}

.loader {
  text-align: center;
  padding: 1.5rem;
  color: #4b5563;
}

.table-wrapper {
  overflow-x: auto;
  border-radius: 0.75rem;
  border: 1px solid #e5e7eb;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.95rem;
}

th,
td {
  padding: 0.9rem 1rem;
  text-align: left;
  border-bottom: 1px solid #f3f4f6;
  vertical-align: top;
}

th {
  background-color: #f9fafb;
  font-weight: 600;
  color: #4b5563;
}

tbody tr:hover {
  background-color: #f4f4ff;
}

.title {
  font-weight: 600;
  color: #111827;
}

.description {
  margin-top: 0.3rem;
  font-size: 0.85rem;
  color: #6b7280;
}

.status-tag {
  display: inline-block;
  padding: 0.3rem 0.75rem;
  border-radius: 999px;
  font-size: 0.8rem;
  font-weight: 600;
}

.status-tag.active {
  background-color: #dcfce7;
  color: #166534;
}

.status-tag.inactive {
  background-color: #fee2e2;
  color: #b91c1c;
}
</style>

