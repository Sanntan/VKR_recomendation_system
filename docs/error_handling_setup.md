# Настройка обработки ошибок и логирования

## Обзор

В проекте реализована комплексная система обработки ошибок и логирования:

1. **Структурированное логирование** для Python (backend + bot)
2. **Централизованный обработчик ошибок** для FastAPI
3. **Sentry** для отслеживания ошибок (Python)
4. **Улучшенная обработка ошибок** в админ-панели (Vue.js)
5. **Опциональная поддержка Sentry** для админ-панели

## Настройка

### 1. Переменные окружения

Добавьте в `.env`:

```env
# Логирование
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Sentry (опционально)
SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
SENTRY_ENVIRONMENT=production  # development, staging, production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% запросов для трейсинга
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

Для админ-панели добавьте в `.env` (или `admin-panel/.env`):

```env
VITE_SENTRY_DSN=https://your-sentry-dsn@sentry.io/project-id
VITE_SENTRY_ENVIRONMENT=production
```

### 2. Установка зависимостей

```bash
# Python зависимости (уже добавлены в requirements.txt)
pip install -r requirements.txt

# Для админ-панели (опционально, только если используете Sentry)
cd admin-panel
npm install @sentry/vue
```

## Использование

### Python (Backend + Bot)

#### Логирование

```python
from src.core.logging_config import get_logger

logger = get_logger(__name__)

logger.info("Информационное сообщение")
logger.error("Ошибка", extra={"context": "дополнительные данные"})
```

#### Исключения

```python
from src.core.exceptions import NotFoundError, ValidationError

# В роутере FastAPI
if not student:
    raise NotFoundError("Студент не найден", details={"participant_id": participant_id})
```

#### Sentry

Ошибки автоматически отправляются в Sentry через обработчики ошибок. Для ручной отправки:

```python
from src.core.sentry_config import capture_exception, capture_message

try:
    # код
except Exception as e:
    capture_exception(e)
    capture_message("Что-то пошло не так", level="error")
```

### Vue.js (Админ-панель)

#### Обработка ошибок в компонентах

```javascript
import { handleError, withErrorHandling } from '@/services/errorHandler.js';

// Вариант 1: Обработка вручную
async function loadData() {
  try {
    const data = await fetchData();
    return data;
  } catch (error) {
    handleError(error, {
      component: 'MyComponent',
      action: 'loadData',
    });
  }
}

// Вариант 2: Использование обертки
const loadData = withErrorHandling(
  async () => {
    return await fetchData();
  },
  { component: 'MyComponent', action: 'loadData' }
);
```

#### Глобальная обработка

Ошибки автоматически обрабатываются через:
- Interceptors в `api/client.js`
- Глобальный обработчик Vue в `main.js`
- Компонент `ErrorNotification.vue` для отображения

## Структура файлов

```
src/
├── core/
│   ├── logging_config.py      # Настройка логирования
│   ├── exceptions.py          # Базовые исключения
│   └── sentry_config.py       # Конфигурация Sentry
├── api/
│   └── middleware/
│       └── error_handler.py   # Обработчики ошибок FastAPI
└── bot/
    └── main.py                # Обработчик ошибок бота

admin-panel/src/
├── services/
│   ├── errorHandler.js       # Обработка ошибок
│   └── sentry.js             # Конфигурация Sentry (опционально)
└── components/
    └── ErrorNotification.vue # Компонент уведомлений
```

## Форматы логов

### Консоль
- Цветной формат для удобства разработки
- Формат: `timestamp - logger - level - message`

### Файл (если настроен)
- JSON формат для структурированного анализа
- Включает: timestamp, level, logger, message, module, function, line, exception

## Мониторинг

### Sentry Dashboard

1. Создайте проект на [sentry.io](https://sentry.io)
2. Получите DSN
3. Добавьте в переменные окружения
4. Ошибки будут автоматически отправляться в Sentry

### Локальные логи

Логи выводятся в консоль. Для записи в файл настройте `log_file` в `setup_logging()`.

## Рекомендации

1. **Используйте структурированные исключения** вместо обычных `Exception`
2. **Добавляйте контекст** через `extra` в логи
3. **Не логируйте чувствительные данные** (пароли, токены)
4. **Настройте Sentry** для production окружения
5. **Используйте разные уровни логирования** для разных окружений

