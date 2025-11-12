<template>
  <section class="card">
    <div class="card-header">
      <div>
        <h2>Поиск студента</h2>
        <p>Введите participant_id для поиска или используйте список ниже</p>
      </div>
    </div>

    <form class="form" @submit.prevent="loadStudent">
      <label class="field">
        <span>participant_id</span>
        <input
          v-model="participantId"
          type="text"
          placeholder="например, test_student_001"
          required
        />
      </label>
      <button type="submit" :disabled="searchLoading">
        {{ searchLoading ? "Загрузка..." : "Найти" }}
      </button>
    </form>

    <div v-if="searchError" class="alert error">
      {{ searchError }}
    </div>

    <div v-if="student" class="student-card">
      <div class="info-row">
        <span class="label">ID студента</span>
        <span>{{ student.id }}</span>
      </div>
      <div class="info-row">
        <span class="label">participant_id</span>
        <span>{{ student.participant_id }}</span>
      </div>
      <div class="info-row">
        <span class="label">Образовательное учреждение</span>
        <span>{{ student.institution || "—" }}</span>
      </div>
      <div class="info-row">
        <span class="label">Направление</span>
        <span>{{ student.direction?.title || "Не указано" }}</span>
      </div>
      <div class="info-row">
        <span class="label">Кластер направления</span>
        <span>{{ student.direction?.cluster_id || "—" }}</span>
      </div>
      <div class="info-row">
        <span class="label">Создан</span>
        <span>{{ formatDate(student.created_at) }}</span>
      </div>
    </div>

    <section class="list-section">
      <header class="list-header">
        <div>
          <h3>Все студенты</h3>
          <p>Показано {{ students.length }} из {{ totalStudents }} записей</p>
        </div>
        <div class="list-controls">
          <label>
            <span>Лимит</span>
            <input type="number" min="5" max="200" v-model.number="listLimit" />
          </label>
          <button type="button" class="secondary" @click="refreshStudents" :disabled="studentsLoading">
            Обновить
          </button>
        </div>
      </header>

      <div v-if="studentsError" class="alert error">
        {{ studentsError }}
      </div>

      <div v-else>
        <div v-if="studentsLoading && !students.length" class="list-loader">
          Загрузка списка студентов...
        </div>

        <ul v-else class="students-list">
          <li
            v-for="item in students"
            :key="item.id"
            :class="{ active: student?.id === item.id }"
            @click="selectStudent(item)"
          >
            <div class="primary">{{ item.participant_id }}</div>
            <div class="secondary">
              {{ item.direction?.title || "Направление не указано" }}
            </div>
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
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { fetchStudentByParticipant, fetchStudents } from "../api/client.js";

const participantId = ref("");
const searchLoading = ref(false);
const searchError = ref("");
const student = ref(null);

const students = ref([]);
const studentsLoading = ref(false);
const studentsError = ref("");
const totalStudents = ref(0);
const listLimit = ref(20);
const nextOffset = ref(0);

const hasMoreStudents = computed(() => students.value.length < totalStudents.value);

function formatDate(dateValue) {
  if (!dateValue) return "—";
  const date = new Date(dateValue);
  if (Number.isNaN(date.getTime())) return dateValue;
  return date.toLocaleString("ru-RU");
}

async function loadStudent() {
  if (!participantId.value) return;

  searchLoading.value = true;
  searchError.value = "";

  try {
    const response = await fetchStudentByParticipant(participantId.value.trim());
    student.value = response;
  } catch (err) {
    console.error(err);
    student.value = null;
    if (err?.response?.status === 404) {
      searchError.value = "Студент не найден";
    } else {
      searchError.value = "Ошибка загрузки данных";
    }
  } finally {
    searchLoading.value = false;
  }
}

function selectStudent(item) {
  student.value = item;
  participantId.value = item.participant_id;
  searchError.value = "";
}

async function loadStudents({ reset = false } = {}) {
  if (reset) {
    students.value = [];
    nextOffset.value = 0;
  }

  studentsLoading.value = true;
  studentsError.value = "";

  try {
    const response = await fetchStudents({
      limit: listLimit.value,
      offset: nextOffset.value
    });
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
.card {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
  padding: 1.75rem;
  background-color: #ffffff;
  border-radius: 12px;
  border: 1px solid #dee2e6;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
}

.card-header h2 {
  margin: 0 0 0.35rem 0;
  font-size: 1.35rem;
}

.card-header p {
  margin: 0;
  color: #6c757d;
  font-size: 0.95rem;
}

.form {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  background-color: #f8f9fa;
  padding: 1rem;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  flex: 1 1 260px;
}

.field span {
  font-weight: 600;
  color: #495057;
  font-size: 0.9rem;
}

input {
  padding: 0.65rem 0.85rem;
  border-radius: 8px;
  border: 1px solid #ced4da;
  transition: border-color 0.2s ease, box-shadow 0.2s ease;
  font-size: 1rem;
  background-color: #ffffff;
  color: #212529;
}

input:focus {
  outline: none;
  border-color: #0d6efd;
  box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.1);
}

input::placeholder {
  color: #adb5bd;
}

button {
  padding: 0.75rem 1.5rem;
  border-radius: 8px;
  border: none;
  background: #0d6efd;
  color: #ffffff;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s ease, transform 0.2s ease, box-shadow 0.2s ease;
}

button.secondary {
  background: #6c757d;
  color: #ffffff;
}

button:hover:not(:disabled) {
  background: #0b5ed7;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(13, 110, 253, 0.25);
}

button.secondary:hover:not(:disabled) {
  background: #5c636a;
}

button:disabled {
  opacity: 0.6;
  cursor: default;
}

.alert {
  padding: 0.85rem 1rem;
  border-radius: 0.75rem;
  font-size: 0.95rem;
}

.alert.error {
  background-color: #f8d7da;
  border: 1px solid #f5c2c7;
  color: #842029;
}

.student-card {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1rem;
  padding: 1.25rem;
  background-color: #f8f9fa;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

.info-row {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  padding: 0.75rem;
  background-color: #ffffff;
  border-radius: 8px;
  border: 1px solid #dee2e6;
}

.label {
  font-size: 0.8rem;
  text-transform: uppercase;
  letter-spacing: 0.02em;
  color: #495057;
  font-weight: 600;
}

.list-section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.list-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 1rem;
  flex-wrap: wrap;
}

.list-header h3 {
  margin: 0;
}

.list-header p {
  margin: 0.25rem 0 0;
  color: #6c757d;
  font-size: 0.9rem;
}

.list-controls {
  display: flex;
  gap: 0.75rem;
  align-items: center;
}

.list-controls label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.85rem;
  color: #495057;
}

.list-controls input {
  width: 90px;
  padding: 0.4rem 0.6rem;
  border-radius: 6px;
  border: 1px solid #ced4da;
  background-color: #ffffff;
  color: #212529;
}

.students-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 0.75rem;
}

.students-list li {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 0.9rem;
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
  background-color: #ffffff;
}

.students-list li:hover {
  border-color: #0d6efd;
  background-color: #f8f9fa;
  box-shadow: 0 2px 8px rgba(13, 110, 253, 0.1);
}

.students-list li.active {
  border-color: #0d6efd;
  background-color: #e7f1ff;
  box-shadow: 0 0 0 3px rgba(13, 110, 253, 0.15);
}

.primary {
  font-weight: 600;
  color: #212529;
}

.secondary {
  font-size: 0.9rem;
  color: #495057;
  margin-top: 0.25rem;
}

.meta {
  margin-top: 0.4rem;
  font-size: 0.75rem;
  color: #6c757d;
}

.list-actions {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin-top: 0.5rem;
}

.list-loader,
.list-end {
  color: #6c757d;
  font-size: 0.9rem;
}
</style>

