<template>
  <TransitionGroup name="error-list" tag="div" class="error-notifications">
    <div
      v-for="error in errors"
      :key="error.id"
      :class="['error-notification', `error-${error.type || 'error'}`]"
    >
      <div class="error-content">
        <div class="error-header">
          <span class="error-icon">{{ getErrorIcon(error.type) }}</span>
          <span class="error-title">{{ error.title || 'Ошибка' }}</span>
          <button class="error-close" @click="removeError(error.id)">×</button>
        </div>
        <div class="error-message">{{ error.message }}</div>
        <details v-if="error.details && showDetails" class="error-details">
          <summary>Детали ошибки</summary>
          <pre>{{ formatDetails(error.details) }}</pre>
        </details>
      </div>
    </div>
  </TransitionGroup>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const errors = ref([]);
const showDetails = ref(process.env.NODE_ENV === 'development');

let errorIdCounter = 0;

function getErrorIcon(type) {
  const icons = {
    error: '❌',
    warning: '⚠️',
    info: 'ℹ️',
    success: '✅',
  };
  return icons[type] || icons.error;
}

function formatDetails(details) {
  if (typeof details === 'string') return details;
  return JSON.stringify(details, null, 2);
}

function addError(error) {
  const id = errorIdCounter++;
  errors.value.push({
    id,
    ...error,
    timestamp: new Date().toISOString(),
  });

  // Автоматически удаляем через 5 секунд (если не критическая ошибка)
  if (error.type !== 'error' || error.statusCode < 500) {
    setTimeout(() => {
      removeError(id);
    }, 5000);
  }
}

function removeError(id) {
  const index = errors.value.findIndex((e) => e.id === id);
  if (index > -1) {
    errors.value.splice(index, 1);
  }
}

function handleGlobalError(event) {
  if (event.error) {
    addError({
      title: 'Необработанная ошибка',
      message: event.error.message || 'Произошла неизвестная ошибка',
      type: 'error',
      details: event.error.stack,
    });
  }
}

onMounted(() => {
  // Регистрируем глобальный обработчик ошибок
  window.addEventListener('error', handleGlobalError);
  window.addEventListener('unhandledrejection', (event) => {
    addError({
      title: 'Необработанное обещание',
      message: event.reason?.message || 'Произошла ошибка при выполнении операции',
      type: 'error',
      details: event.reason,
    });
  });

  // Регистрируем store для глобального доступа
  window.errorStore = {
    addError,
    removeError,
    errors,
  };
});

onUnmounted(() => {
  window.removeEventListener('error', handleGlobalError);
  delete window.errorStore;
});
</script>

<style scoped>
.error-notifications {
  position: fixed;
  top: 20px;
  right: 20px;
  z-index: 10000;
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-width: 400px;
}

.error-notification {
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  padding: 16px;
  border-left: 4px solid #dc3545;
  animation: slideIn 0.3s ease-out;
}

.error-warning {
  border-left-color: #ffc107;
}

.error-info {
  border-left-color: #17a2b8;
}

.error-success {
  border-left-color: #28a745;
}

.error-content {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.error-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.error-icon {
  font-size: 1.2em;
}

.error-title {
  flex: 1;
}

.error-close {
  background: none;
  border: none;
  font-size: 1.5em;
  cursor: pointer;
  color: #6c757d;
  padding: 0;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

.error-close:hover {
  color: #343a40;
}

.error-message {
  color: #495057;
  font-size: 0.9em;
}

.error-details {
  margin-top: 8px;
  font-size: 0.85em;
}

.error-details summary {
  cursor: pointer;
  color: #6c757d;
  margin-bottom: 4px;
}

.error-details pre {
  background: #f8f9fa;
  padding: 8px;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.8em;
  color: #495057;
}

@keyframes slideIn {
  from {
    transform: translateX(100%);
    opacity: 0;
  }
  to {
    transform: translateX(0);
    opacity: 1;
  }
}

.error-list-enter-active,
.error-list-leave-active {
  transition: all 0.3s ease;
}

.error-list-enter-from {
  transform: translateX(100%);
  opacity: 0;
}

.error-list-leave-to {
  transform: translateX(100%);
  opacity: 0;
}
</style>

