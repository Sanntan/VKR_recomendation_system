/**
 * Конфигурация Sentry для админ-панели (опционально).
 * Для использования установите @sentry/vue и настройте DSN.
 */

/**
 * Инициализирует Sentry для отслеживания ошибок.
 * @param {string} dsn - Sentry DSN
 * @param {string} environment - Окружение (development, production, staging)
 */
export function initSentry(dsn, environment = 'development') {
  // Проверяем, установлен ли Sentry
  if (typeof window === 'undefined' || !dsn) {
    console.info('Sentry не настроен (DSN не указан)');
    return;
  }

  // Динамически импортируем Sentry только если он установлен
  import('@sentry/vue')
    .then((Sentry) => {
      Sentry.init({
        dsn,
        environment,
        integrations: [
          new Sentry.BrowserTracing(),
          new Sentry.Replay({
            maskAllText: true,
            blockAllMedia: true,
          }),
        ],
        tracesSampleRate: environment === 'production' ? 0.1 : 1.0,
        replaysSessionSampleRate: 0.1,
        replaysOnErrorSampleRate: 1.0,
      });

      console.info('Sentry инициализирован');
    })
    .catch((error) => {
      console.warn('Не удалось инициализировать Sentry:', error);
      console.info('Установите @sentry/vue для использования: npm install @sentry/vue');
    });
}

/**
 * Устанавливает пользователя для Sentry.
 * @param {Object} user - Информация о пользователе
 */
export function setSentryUser(user) {
  if (window.Sentry) {
    window.Sentry.setUser(user);
  }
}

