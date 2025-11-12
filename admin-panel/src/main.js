import { createApp } from "vue";
import App from "./App.vue";
import ErrorNotification from "./components/ErrorNotification.vue";
import { initSentry } from "./services/sentry.js";

import "./styles/main.css";

// Инициализация Sentry (опционально, если настроен DSN)
const sentryDsn = import.meta.env.VITE_SENTRY_DSN;
if (sentryDsn) {
  initSentry(sentryDsn, import.meta.env.VITE_SENTRY_ENVIRONMENT || "development");
}

const app = createApp(App);

// Добавляем глобальный компонент для уведомлений об ошибках
app.component("ErrorNotification", ErrorNotification);

// Глобальная обработка ошибок Vue
app.config.errorHandler = (err, instance, info) => {
  console.error("Vue Error:", err, info);
  if (window.errorStore) {
    window.errorStore.addError({
      title: "Ошибка компонента",
      message: err.message || "Произошла ошибка в компоненте",
      type: "error",
      details: {
        component: instance?.$options?.name || "unknown",
        info,
        stack: err.stack,
      },
    });
  }
};

app.mount("#app");
