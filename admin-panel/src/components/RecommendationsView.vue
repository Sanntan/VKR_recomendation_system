<template>
  <section class="card recommendations-card">
    <header class="card-header">
      <div>
        <h2>Рекомендации по студентам</h2>
        <p>Выберите студента слева, чтобы увидеть закреплённые рекомендации и при необходимости запустить пересчёт.</p>
      </div>
    </header>

    <div class="layout">
      <aside class="students-column">
        <div class="students-toolbar">
          <label class="input-group">
            <span>Фильтр по participant_id</span>
            <input
              v-model.trim="studentFilter"
              type="text"
              placeholder="Начните вводить participant_id"
            />
          </label>
          <div class="toolbar-actions">
            <label>
              <span>Лимит</span>
              <input type="number" min="5" max="200" v-model.number="listLimit" />
            </label>
            <button type="button" class="secondary" @click="refreshStudents" :disabled="studentsLoading">
              Обновить
            </button>
          </div>
        </div>

        <div v-if="studentsError" class="alert error">
          {{ studentsError }}
        </div>

        <div v-else class="students-list-wrapper">
          <div v-if="studentsLoading && !students.length" class="list-loader">
            Загрузка студентов...
          </div>

          <ul v-else class="students-list">
            <li
              v-for="item in filteredStudents"
              :key="item.id"
              :class="{ active: selectedStudent?.id === item.id }"
              @click="selectStudent(item)"
            >
              <div class="primary">{{ item.participant_id }}</div>
              <div class="secondary">{{ item.direction?.title || "Направление не указано" }}</div>
              <div class="meta">
                {{ item.institution || "—" }}
                <span v-if="item.created_at">· {{ formatDate(item.created_at) }}</span>
              </div>
            </li>
          </ul>

          <div class="list-actions">
            <button
              type="button"
              class="secondary"
              v-if="hasMoreStudents"
              @click="loadStudents()"
              :disabled="studentsLoading"
            >
              {{ studentsLoading ? "Загрузка..." : "Показать ещё" }}
            </button>
            <span v-else-if="totalStudents" class="list-end">
              Все студенты загружены
            </span>
          </div>
        </div>
      </aside>

      <div class="details-column">
        <div v-if="!selectedStudent" class="placeholder">
          Выберите студента из списка, чтобы посмотреть рекомендации.
        </div>

        <div v-else class="recommendations-panel">
          <header class="student-summary">
            <div>
              <h3>{{ selectedStudent.participant_id }}</h3>
              <p>
                {{ selectedStudent.institution || "Учебное заведение не указано" }}
                <br />
                <span v-if="selectedStudent.direction">
                  Направление: {{ selectedStudent.direction.title }}
                  <br />
                  Кластер: {{ selectedStudent.direction.cluster_id }}
                </span>
              </p>
            </div>
            <div class="summary-actions">
              <label class="input-group inline">
                <span>Лимит</span>
                <input type="number" min="1" max="100" v-model.number="limit" />
              </label>
              <label class="input-group inline">
                <span>Мин. score</span>
                <input type="number" min="0" max="1" step="0.01" v-model.number="minScore" />
              </label>
              <button type="button" @click="loadRecommendations" :disabled="recommendationsLoading">
                {{ recommendationsLoading ? "Обновление..." : "Обновить" }}
              </button>
              <button
                type="button"
                class="ghost"
                @click="recalculate"
                :disabled="recalculating || recommendationsLoading"
              >
                {{ recalculating ? "Пересчёт..." : "Пересчитать" }}
              </button>
            </div>
          </header>

          <div v-if="recommendationsError" class="alert error">
            {{ recommendationsError }}
          </div>

          <div v-else-if="recommendationsLoading" class="loader">
            Загрузка рекомендаций...
          </div>

          <div v-else-if="recommendationRows.length" class="recommendations-grid">
            <article v-for="item in recommendationRows" :key="item.id" class="recommendation-card">
              <header>
                <h4>{{ item.event?.title || "Мероприятие" }}</h4>
                <span class="score" :class="{ high: (item.score ?? 0) >= 0.7 }">
                  {{ item.score != null ? item.score.toFixed(3) : "—" }}
                </span>
              </header>
              <dl>
                <div>
                  <dt>ID рекомендации</dt>
                  <dd>{{ item.id }}</dd>
                </div>
                <div>
                  <dt>ID события</dt>
                  <dd>{{ item.event_id }}</dd>
                </div>
                <div v-if="item.event?.format">
                  <dt>Формат</dt>
                  <dd>{{ item.event.format }}</dd>
                </div>
                <div>
                  <dt>Создано</dt>
                  <dd>{{ formatDate(item.created_at) }}</dd>
                </div>
                <div v-if="item.event?.start_date || item.event?.end_date">
                  <dt>Даты</dt>
                  <dd>
                    {{ formatDate(item.event?.start_date) }}
                    <template v-if="item.event?.end_date"> → {{ formatDate(item.event?.end_date) }}</template>
                  </dd>
                </div>
                <div v-if="item.event?.link">
                  <dt>Ссылка</dt>
                  <dd>
                    <a :href="item.event.link" target="_blank" rel="noopener">Открыть</a>
                  </dd>
                </div>
              </dl>
            </article>
          </div>

          <p v-else class="empty-state">
            Рекомендаций нет. Попробуйте пересчитать или выбрать другого студента.
          </p>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import {
  fetchEventsBulk,
  fetchRecommendationsByStudent,
  fetchStudents,
  recalculateRecommendationsForStudent
} from "../api/client.js";

const students = ref([]);
const studentsLoading = ref(false);
const studentsError = ref("");
const totalStudents = ref(0);
const listLimit = ref(20);
const nextOffset = ref(0);
const studentFilter = ref("");

const selectedStudent = ref(null);
const limit = ref(10);
const minScore = ref(0);

const recommendations = ref([]);
const recommendationsLoading = ref(false);
const recommendationsError = ref("");
const recalculating = ref(false);
const eventsMap = ref(new Map());

const hasMoreStudents = computed(() => students.value.length < totalStudents.value);
const filteredStudents = computed(() => {
  if (!studentFilter.value) {
    return students.value;
  }
  const query = studentFilter.value.toLowerCase();
  return students.value.filter((student) => student.participant_id.toLowerCase().includes(query));
});

const recommendationRows = computed(() =>
  recommendations.value.map((item) => ({
    ...item,
    event: eventsMap.value.get(item.event_id) ?? null
  }))
);

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("ru-RU");
}

async function loadStudents({ reset = false } = {}) {
  if (reset) {
    students.value = [];
    nextOffset.value = 0;
  }

  studentsLoading.value = true;
  studentsError.value = "";

  try {
    const response = await fetchStudents({ limit: listLimit.value, offset: nextOffset.value });
    const fetched = response.students ?? [];
    totalStudents.value = response.total ?? fetched.length;

    if (reset) {
      students.value = fetched;
    } else {
      const existing = new Set(students.value.map((item) => item.id));
      students.value = [...students.value, ...fetched.filter((item) => !existing.has(item.id))];
    }

    nextOffset.value = (response.offset ?? nextOffset.value) + fetched.length;
  } catch (err) {
    console.error(err);
    studentsError.value = "Не удалось загрузить список студентов";
  } finally {
    studentsLoading.value = false;
  }
}

function refreshStudents() {
  loadStudents({ reset: true });
}

function selectStudent(student) {
  selectedStudent.value = student;
  recommendations.value = [];
  eventsMap.value = new Map();
  recommendationsError.value = "";
  loadRecommendations();
}

async function loadRecommendations() {
  if (!selectedStudent.value?.id) {
    return;
  }

  recommendationsLoading.value = true;
  recommendationsError.value = "";

  try {
    const response = await fetchRecommendationsByStudent(selectedStudent.value.id, { limit: limit.value });
    recommendations.value = response ?? [];

    if (!recommendations.value.length) {
      eventsMap.value = new Map();
      return;
    }

    const eventIds = recommendations.value.map((item) => item.event_id);
    const eventsResponse = await fetchEventsBulk(eventIds);
    const map = new Map();
    (eventsResponse.events ?? []).forEach((event) => {
      map.set(event.id, event);
    });
    eventsMap.value = map;
  } catch (err) {
    console.error(err);
    recommendations.value = [];
    eventsMap.value = new Map();
    if (err?.response?.status === 404) {
      recommendationsError.value = "Рекомендации не найдены";
    } else {
      recommendationsError.value = "Не удалось загрузить рекомендации";
    }
  } finally {
    recommendationsLoading.value = false;
  }
}

async function recalculate() {
  if (!selectedStudent.value?.id) {
    return;
  }

  recalculating.value = true;
  recommendationsError.value = "";

  try {
    await recalculateRecommendationsForStudent(selectedStudent.value.id, { minScore: minScore.value || 0 });
    await loadRecommendations();
  } catch (err) {
    console.error(err);
    recommendationsError.value = "Ошибка пересчёта рекомендаций";
  } finally {
    recalculating.value = false;
  }
}

watch(listLimit, () => {
  if (listLimit.value < 5) {
    listLimit.value = 5;
  } else if (listLimit.value > 200) {
    listLimit.value = 200;
  }
  refreshStudents();
});

onMounted(() => {
  loadStudents({ reset: true });
});
</script>

<style scoped>
.recommendations-card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.layout {
  display: grid;
  grid-template-columns: 340px 1fr;
  gap: 1.5rem;
  align-items: start;
}

.students-column {
  border: 1px solid #e5e7eb;
  border-radius: 1rem;
  padding: 1rem;
  background-color: #f8fafc;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.students-toolbar {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.input-group {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
  color: #4b5563;
}

.input-group.inline {
  min-width: 120px;
}

.input-group input {
  padding: 0.5rem 0.7rem;
  border-radius: 0.7rem;
  border: 1px solid #d1d5db;
}

.toolbar-actions {
  display: flex;
  gap: 0.75rem;
  align-items: center;
  flex-wrap: wrap;
}

.students-list-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.students-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

.students-list li {
  padding: 0.75rem;
  border-radius: 0.75rem;
  border: 1px solid #e2e8f0;
  background-color: #ffffff;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.students-list li:hover {
  border-color: #a5b4fc;
  box-shadow: 0 6px 12px rgba(99, 102, 241, 0.12);
}

.students-list li.active {
  border-color: #6366f1;
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
}

.primary {
  font-weight: 600;
  color: #111827;
}

.secondary {
  font-size: 0.9rem;
  color: #4b5563;
  margin-top: 0.25rem;
}

.meta {
  margin-top: 0.35rem;
  font-size: 0.75rem;
  color: #6b7280;
}

.list-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.list-end,
.list-loader {
  font-size: 0.85rem;
  color: #6b7280;
}

.details-column {
  border: 1px solid #e5e7eb;
  border-radius: 1rem;
  padding: 1.25rem;
  min-height: 320px;
  background-color: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.placeholder {
  margin: 0;
  color: #64748b;
  font-style: italic;
}

.recommendations-panel {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.student-summary {
  display: flex;
  justify-content: space-between;
  gap: 1.5rem;
  flex-wrap: wrap;
}

.student-summary h3 {
  margin: 0 0 0.4rem 0;
}

.student-summary p {
  margin: 0;
  color: #4b5563;
  font-size: 0.95rem;
  line-height: 1.4;
}

.summary-actions {
  display: flex;
  gap: 0.6rem;
  align-items: center;
  flex-wrap: wrap;
}

button {
  padding: 0.65rem 1.2rem;
  border-radius: 0.75rem;
  border: none;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

button.secondary {
  background: #eef2ff;
  color: #312e81;
}

button.ghost {
  background-color: rgba(99, 102, 241, 0.12);
  color: #312e81;
}

button:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: 0 8px 16px rgba(99, 102, 241, 0.2);
}

button:disabled {
  opacity: 0.6;
  cursor: default;
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

.loader {
  color: #6b7280;
}

.recommendations-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 1rem;
}

.recommendation-card {
  padding: 1.2rem;
  border-radius: 1rem;
  border: 1px solid #e0e7ff;
  background-color: #eef2ff;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.recommendation-card header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.recommendation-card h4 {
  margin: 0;
  font-size: 1rem;
  color: #312e81;
}

.score {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 60px;
  padding: 0.35rem 0.6rem;
  border-radius: 999px;
  background-color: #ddd6fe;
  color: #4c1d95;
  font-weight: 700;
}

.score.high {
  background-color: #bbf7d0;
  color: #166534;
}

dl {
  margin: 0;
  display: grid;
  gap: 0.6rem;
}

dt {
  font-size: 0.8rem;
  color: #4c1d95;
  font-weight: 600;
}

dd {
  margin: 0;
  font-size: 0.95rem;
  color: #1f2937;
}

.empty-state {
  margin: 0;
  color: #6b7280;
  font-style: italic;
}

@media (max-width: 960px) {
  .layout {
    grid-template-columns: 1fr;
  }

  .students-column {
    order: 2;
  }

  .details-column {
    order: 1;
  }
}
</style>

