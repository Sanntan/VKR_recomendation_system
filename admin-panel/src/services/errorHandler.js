/**
 * Централизованный обработчик ошибок для админ-панели.
 */

/**
 * Класс для обработки ошибок приложения.
 */
export class AppError extends Error {
  constructor(message, statusCode = 500, details = null) {
    super(message);
    this.name = 'AppError';
    this.statusCode = statusCode;
    this.details = details;
    this.timestamp = new Date().toISOString();
  }
}

/**
 * Обрабатывает ошибки API запросов.
 * @param {Error} error - Ошибка из axios
 * @returns {AppError} Обработанная ошибка
 */
export function handleApiError(error) {
  console.error('API Error:', error);

  // Ошибка сети
  if (!error.response) {
    return new AppError(
      'Ошибка сети. Проверьте подключение к интернету.',
      0,
      { originalError: error.message }
    );
  }

  const { status, data } = error.response;
  const message = data?.message || data?.detail || error.message || 'Неизвестная ошибка';
  const details = data?.details || null;

  // Специальная обработка для разных статусов
  switch (status) {
    case 400:
      return new AppError(`Ошибка валидации: ${message}`, 400, details);
    case 401:
      return new AppError('Требуется авторизация', 401, details);
    case 403:
      return new AppError('Доступ запрещен', 403, details);
    case 404:
      return new AppError('Ресурс не найден', 404, details);
    case 422:
      return new AppError(`Ошибка валидации данных: ${message}`, 422, details);
    case 500:
      return new AppError('Внутренняя ошибка сервера', 500, details);
    case 502:
      return new AppError('Ошибка внешнего сервиса', 502, details);
    case 503:
      return new AppError('Сервис временно недоступен', 503, details);
    default:
      return new AppError(message, status, details);
  }
}

/**
 * Показывает пользователю сообщение об ошибке.
 * @param {AppError|Error} error - Ошибка
 * @param {Object} options - Опции отображения
 */
export function showErrorToUser(error, options = {}) {
  const {
    title = 'Ошибка',
    showDetails = false,
    duration = 5000,
  } = options;

  const message = error instanceof AppError ? error.message : error.message;
  const details = error instanceof AppError && error.details ? error.details : null;

  // В реальном приложении можно использовать toast-уведомления
  // Например, vue-toastification или подобное
  console.error(`[${title}]`, message);
  if (showDetails && details) {
    console.error('Детали:', details);
  }

  // Можно добавить глобальное хранилище для ошибок
  // и показывать их через компонент уведомлений
  if (window.errorStore) {
    window.errorStore.addError({
      title,
      message,
      details: showDetails ? details : null,
      timestamp: new Date().toISOString(),
    });
  }

  // Альтернатива: можно использовать window.alert для критических ошибок
  // if (error.statusCode >= 500) {
  //   alert(`${title}: ${message}`);
  // }
}

/**
 * Обрабатывает ошибку и логирует её.
 * @param {Error} error - Ошибка
 * @param {Object} context - Контекст ошибки (компонент, действие и т.д.)
 */
export function handleError(error, context = {}) {
  const errorInfo = {
    message: error.message,
    stack: error.stack,
    context,
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent,
    url: window.location.href,
  };

  // Логируем в консоль
  console.error('Application Error:', errorInfo);

  // Отправляем в Sentry (если настроен)
  if (window.Sentry) {
    window.Sentry.captureException(error, {
      contexts: {
        custom: context,
      },
      tags: {
        component: context.component || 'unknown',
        action: context.action || 'unknown',
      },
    });
  }

  // Показываем пользователю
  const appError = error instanceof AppError ? error : handleApiError(error);
  showErrorToUser(appError, {
    title: context.title || 'Произошла ошибка',
    showDetails: process.env.NODE_ENV === 'development',
  });

  return appError;
}

/**
 * Обертка для async функций с обработкой ошибок.
 * @param {Function} asyncFn - Асинхронная функция
 * @param {Object} context - Контекст для логирования
 * @returns {Function} Обернутая функция
 */
export function withErrorHandling(asyncFn, context = {}) {
  return async (...args) => {
    try {
      return await asyncFn(...args);
    } catch (error) {
      handleError(error, context);
      throw error;
    }
  };
}

/**
 * Создает обработчик ошибок для Vue компонента.
 * @param {Object} component - Vue компонент
 * @param {String} componentName - Имя компонента
 * @returns {Function} Обработчик ошибок
 */
export function createErrorHandler(componentName) {
  return (error, instance, info) => {
    handleError(error, {
      component: componentName,
      vueInfo: info,
      instance: instance?.$options?.name || 'unknown',
    });
  };
}

