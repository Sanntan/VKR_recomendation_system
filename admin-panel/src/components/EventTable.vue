<script setup>
import { computed } from "vue";

const props = defineProps({
  items: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  showScore: {
    type: Boolean,
    default: false,
  },
});

const hasData = computed(() => props.items && props.items.length > 0);

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleDateString("ru-RU", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}
</script>

<template>
  <div class="event-table">
    <div v-if="loading" class="loader">Загрузка...</div>
    <div v-else-if="!hasData" class="placeholder">
      Данные отсутствуют.
    </div>
    <div v-else class="table-wrapper">
      <table>
        <thead>
          <tr>
            <th>Название</th>
            <th>Дата</th>
            <th>Формат</th>
            <th v-if="showScore">Score</th>
            <th>👍</th>
            <th>👎</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="event in items" :key="event.id">
            <td>
              <div class="title">{{ event.title }}</div>
              <div v-if="event.short_description" class="description">
                {{ event.short_description }}
              </div>
            </td>
            <td>{{ formatDate(event.start_date) }}</td>
            <td>{{ event.format ?? "—" }}</td>
            <td v-if="showScore">
              <span v-if="typeof event.score === 'number'">
                {{ event.score.toFixed(3) }}
              </span>
              <span v-else>—</span>
            </td>
            <td>{{ event.likes_count ?? 0 }}</td>
            <td>{{ event.dislikes_count ?? 0 }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>


