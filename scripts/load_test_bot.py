"""Инструмент нагрузочного тестирования телеграм-бота.

По умолчанию скрипт разворачивает ``Application`` бота с подмененным транспортом
запросов и эмулирует интенсивное взаимодействие нескольких пользователей
внутри процесса (синтетический режим). Дополнительно доступен режим ``live``:
в нём используется реальный Bot API Telegram и сценарии отправляются в указанные
чаты, что позволяет проверить поведение бота в реальной среде.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import signal
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple
from uuid import uuid4

from dotenv import load_dotenv
from telegram import Update
from telegram.request import BaseRequest, RequestData
from telegram.error import NetworkError, RetryAfter, TimedOut

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()
os.environ.setdefault("BOT_TOKEN", "TEST:TOKEN")

from src.bot.main import build_application


SCENARIOS_REQUIRING_CALLBACKS: Set[str] = {"full", "menu_spam", "feedback_loop"}


CURRENT_METRICS: Optional["LoadTestMetrics"] = None


class FakeBotAPIRequest(BaseRequest):
    """Заменитель ``BaseRequest``, который не делает HTTP-запросы."""

    def __init__(self, artificial_delay: float = 0.0) -> None:
        super().__init__()
        self._read_timeout: Optional[float] = None
        self._message_ids = count(start=1)
        self._artificial_delay = artificial_delay
        self.logger = logging.getLogger(self.__class__.__name__)

    @property
    def read_timeout(self) -> Optional[float]:
        return self._read_timeout

    async def initialize(self) -> None:
        self.logger.debug("FakeBotAPIRequest initialized")

    async def shutdown(self) -> None:
        self.logger.debug("FakeBotAPIRequest shutdown")

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        **_: Any,
    ) -> tuple[int, bytes]:
        if self._artificial_delay:
            await asyncio.sleep(self._artificial_delay)

        parameters = request_data.parameters if request_data else {}
        api_method = url.rsplit("/", 1)[-1]
        self.logger.debug("Bot API call %s with params %s", api_method, parameters)

        payload: Dict[str, Any] | bool
        method_name = api_method.lower()
        if method_name in {"sendmessage", "editmessagetext"}:
            payload = {
                "message_id": parameters.get("message_id", next(self._message_ids)),
                "date": int(time.time()),
                "chat": {
                    "id": parameters.get("chat_id", parameters.get("message_id", 0)),
                    "type": "private",
                },
                "text": parameters.get("text", ""),
                "from": {
                    "id": 0,
                    "is_bot": True,
                    "first_name": "LoadTester",
                },
            }
        elif method_name == "answercallbackquery":
            payload = True
        elif method_name == "getme":
            payload = {
                "id": 0,
                "is_bot": True,
                "first_name": "LoadTester",
                "username": "load_test_bot",
                "can_join_groups": False,
                "can_read_all_group_messages": False,
                "supports_inline_queries": False,
            }
        else:
            payload = True

        body = json.dumps({"ok": True, "result": payload}).encode()
        return 200, body


class LiveRateLimiter:
    """Ограничивает частоту запросов в live-режиме, чтобы уважать лимиты Bot API."""

    def __init__(self, global_rate: float, per_chat_rate: float) -> None:
        self._global_interval = 1.0 / global_rate if global_rate > 0 else 0.0
        self._per_chat_interval = 1.0 / per_chat_rate if per_chat_rate > 0 else 0.0
        self._lock = asyncio.Lock()
        self._last_global_ts = 0.0
        self._per_chat_last: Dict[int, float] = {}

    async def throttle(self, chat_id: Optional[int]) -> None:
        if self._global_interval <= 0.0 and self._per_chat_interval <= 0.0:
            return

        async with self._lock:
            now = time.perf_counter()
            wait_time = 0.0
            if self._global_interval > 0.0:
                wait_time = max(0.0, self._last_global_ts + self._global_interval - now)
            if self._per_chat_interval > 0.0 and chat_id is not None:
                last_chat_ts = self._per_chat_last.get(chat_id, 0.0)
                wait_time = max(wait_time, last_chat_ts + self._per_chat_interval - now)

            if wait_time > 0:
                await asyncio.sleep(wait_time)
                now = time.perf_counter()

            if self._global_interval > 0.0:
                self._last_global_ts = now
            if self._per_chat_interval > 0.0 and chat_id is not None:
                self._per_chat_last[chat_id] = now

@dataclass
class LoadTestMetrics:
    """Сбор метрик по длительности и ошибкам."""

    latencies: List[float] = field(default_factory=list)
    per_type_latencies: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    latency_records: List[Tuple[str, float]] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    total_updates: int = 0
    start_ts: float = field(default_factory=time.perf_counter)
    end_ts: float = 0.0

    def record(self, update: Update, duration: float, exc: Optional[BaseException] = None) -> None:
        global CURRENT_METRICS
        self.total_updates += 1
        self.latencies.append(duration)
        update_type = "callback" if update.callback_query else "message" if update.message else "other"
        self.per_type_latencies[update_type].append(duration)
        self.latency_records.append((update_type, duration))

        if exc is not None:
            self.errors.append(f"{type(exc).__name__}: {exc}")

        CURRENT_METRICS = self

    def finish(self) -> None:
        global CURRENT_METRICS
        now = time.perf_counter()
        if not self.start_ts:
            self.start_ts = now
        self.end_ts = max(self.end_ts, now)
        CURRENT_METRICS = self

    @property
    def duration(self) -> float:
        effective_end = self.end_ts or time.perf_counter()
        return max(effective_end - self.start_ts, 0.0)

    @staticmethod
    def _quantiles(values: Iterable[float]) -> Dict[str, float]:
        data = list(values)
        if not data:
            return {"avg": 0.0, "median": 0.0, "p95": 0.0, "p99": 0.0}

        avg = statistics.mean(data)
        median = statistics.median(data)
        if len(data) == 1:
            value = data[0]
            return {"avg": avg, "median": median, "p95": value, "p99": value}

        percentiles = statistics.quantiles(data, n=100, method="inclusive")
        return {"avg": avg, "median": median, "p95": percentiles[94], "p99": percentiles[98]}

    def summary(self) -> Dict[str, Any]:
        throughput = self.total_updates / self.duration if self.duration > 0 else 0.0
        return {
            "total_updates": self.total_updates,
            "errors": len(self.errors),
            "duration_sec": self.duration,
            "throughput_rps": throughput,
            "latency_overall": self._quantiles(self.latencies),
            "latency_by_type": {
                key: self._quantiles(values) for key, values in self.per_type_latencies.items()
            },
            "error_messages": self.errors,
        }

    def dump(self, metrics_path: Path, raw_metrics_path: Optional[Path] = None) -> None:
        metrics_path.parent.mkdir(parents=True, exist_ok=True)
        with metrics_path.open("w", encoding="utf-8") as fp:
            json.dump(self.summary(), fp, ensure_ascii=False, indent=2)

        if raw_metrics_path:
            raw_metrics_path.parent.mkdir(parents=True, exist_ok=True)
            with raw_metrics_path.open("w", encoding="utf-8") as fp:
                fp.write("update_index,type,latency_ms\n")
                for idx, (update_type, latency) in enumerate(self.latency_records, start=1):
                    fp.write(f"{idx},{update_type},{latency * 1000:.3f}\n")


@dataclass
class LoadPhase:
    """Описание отдельной фазы нагрузочного профиля."""

    label: str
    users: int
    iterations: int
    concurrency: int
    inter_update_delay: float
    valid_email_ratio: float
    scenario: Optional[str] = None
    transport_delay: Optional[float] = None

    def apply(self, base_args: argparse.Namespace) -> argparse.Namespace:
        """Создаёт копию аргументов с параметрами текущей фазы."""

        phase_args = argparse.Namespace(**vars(base_args))
        phase_args.users = max(1, int(self.users))
        phase_args.iterations = max(1, int(self.iterations))
        phase_args.concurrency = max(1, int(self.concurrency))
        phase_args.inter_update_delay = max(0.0, float(self.inter_update_delay))
        phase_args.valid_email_ratio = min(max(float(self.valid_email_ratio), 0.0), 1.0)
        if self.scenario is not None:
            phase_args.scenario = self.scenario
        if self.transport_delay is not None:
            phase_args.transport_delay = max(0.0, float(self.transport_delay))
        return phase_args


def _clamp_ratio(value: float) -> float:
    return min(max(float(value), 0.0), 1.0)


def _scale_int(value: int, factor: float, minimum: int = 1) -> int:
    scaled = int(value * factor)
    return max(minimum, scaled)


def _suffix_path(path: Path, label: str) -> Path:
    safe_label = label.replace(" ", "_")
    return path.with_name(f"{path.stem}_{safe_label}{path.suffix}")


def build_profile_phases(args: argparse.Namespace) -> List[LoadPhase]:
    """Формирует последовательность фаз для выбранного профиля нагрузки."""

    profile = getattr(args, "profile", "single")
    base_users = max(1, int(args.users))
    base_iterations = max(1, int(args.iterations))
    base_concurrency = max(1, int(args.concurrency))
    base_delay = max(0.0, float(args.inter_update_delay))
    base_ratio = _clamp_ratio(args.valid_email_ratio)
    synthetic_mode = args.mode == "synthetic"

    if profile == "single":
        return [
            LoadPhase(
                label="single",
                users=base_users,
                iterations=base_iterations,
                concurrency=base_concurrency,
                inter_update_delay=base_delay,
                valid_email_ratio=base_ratio,
                scenario=args.scenario,
                transport_delay=args.transport_delay,
            )
        ]

    phases: List[LoadPhase] = []

    if profile == "stress":
        phases.append(
            LoadPhase(
                label="warmup",
                users=_scale_int(base_users, 0.5),
                iterations=base_iterations,
                concurrency=_scale_int(base_concurrency, 0.5),
                inter_update_delay=max(base_delay, 0.05),
                valid_email_ratio=base_ratio,
                scenario=args.scenario,
                transport_delay=args.transport_delay,
            )
        )
        phases.append(
            LoadPhase(
                label="baseline",
                users=base_users,
                iterations=base_iterations,
                concurrency=base_concurrency,
                inter_update_delay=base_delay,
                valid_email_ratio=base_ratio,
                scenario=args.scenario,
                transport_delay=args.transport_delay,
            )
        )
        high_scenario = "menu_spam" if synthetic_mode else "text_storm"
        phases.append(
            LoadPhase(
                label="scale_up",
                users=_scale_int(base_users, 2.0),
                iterations=_scale_int(base_iterations, 2.0),
                concurrency=max(base_concurrency * 3, base_concurrency + 20),
                inter_update_delay=base_delay / 2 if base_delay else 0.0,
                valid_email_ratio=max(base_ratio, 0.9),
                scenario=high_scenario,
                transport_delay=0.0 if synthetic_mode else None,
            )
        )
        phases.append(
            LoadPhase(
                label="breaking_point",
                users=_scale_int(base_users, 4.0),
                iterations=max(_scale_int(base_iterations, 3.0), base_iterations + 5),
                concurrency=max(base_concurrency * 5, base_concurrency + 80, 50),
                inter_update_delay=0.0,
                valid_email_ratio=1.0,
                scenario=high_scenario,
                transport_delay=0.0 if synthetic_mode else None,
            )
        )
        return phases

    if profile == "spike":
        spike_scenario = "menu_spam" if synthetic_mode else "text_storm"
        phases.append(
            LoadPhase(
                label="baseline",
                users=base_users,
                iterations=base_iterations,
                concurrency=base_concurrency,
                inter_update_delay=base_delay,
                valid_email_ratio=base_ratio,
                scenario=args.scenario,
                transport_delay=args.transport_delay,
            )
        )
        phases.append(
            LoadPhase(
                label="spike_peak",
                users=max(_scale_int(base_users, 6.0), base_users + 25),
                iterations=1,
                concurrency=max(base_concurrency * 6, base_concurrency + 100),
                inter_update_delay=0.0,
                valid_email_ratio=1.0,
                scenario=spike_scenario,
                transport_delay=0.0 if synthetic_mode else None,
            )
        )
        phases.append(
            LoadPhase(
                label="recovery",
                users=base_users,
                iterations=max(1, base_iterations // 2),
                concurrency=max(1, base_concurrency // 2),
                inter_update_delay=max(base_delay, 0.1),
                valid_email_ratio=base_ratio,
                scenario=args.scenario,
                transport_delay=args.transport_delay,
            )
        )
        return phases

    if profile == "soak":
        soak_scenario = "menu_spam" if synthetic_mode else "text_storm"
        phases.append(
            LoadPhase(
                label="warmup",
                users=base_users,
                iterations=max(1, base_iterations // 2),
                concurrency=max(1, base_concurrency // 2),
                inter_update_delay=max(base_delay, 0.05),
                valid_email_ratio=base_ratio,
                scenario=args.scenario,
                transport_delay=args.transport_delay,
            )
        )
        phases.append(
            LoadPhase(
                label="soak",
                users=base_users,
                iterations=max(base_iterations * 10, base_iterations + 20),
                concurrency=base_concurrency,
                inter_update_delay=max(base_delay, 0.05),
                valid_email_ratio=base_ratio,
                scenario=soak_scenario,
                transport_delay=args.transport_delay,
            )
        )
        phases.append(
            LoadPhase(
                label="chaos",
                users=base_users,
                iterations=base_iterations,
                concurrency=base_concurrency,
                inter_update_delay=0.0,
                valid_email_ratio=0.2,
                scenario=soak_scenario,
                transport_delay=args.transport_delay if synthetic_mode else None,
            )
        )
        return phases

    # На неизвестный профиль возвращаем одиночную фазу для совместимости
    return [
        LoadPhase(
            label="single",
            users=base_users,
            iterations=base_iterations,
            concurrency=base_concurrency,
            inter_update_delay=base_delay,
            valid_email_ratio=base_ratio,
            scenario=args.scenario,
            transport_delay=args.transport_delay,
        )
    ]


class ScenarioFactory:
    """Формирует последовательность ``Update`` для симуляции пользователя."""

    def __init__(
        self,
        bot,  # type: ignore[no-untyped-def]
        valid_email_ratio: float,
        scenario: str = "full",
    ) -> None:
        self.bot = bot
        self.valid_email_ratio = valid_email_ratio
        self._update_ids = count(start=1)
        self._message_ids = count(start=10_000)
        self.scenario = scenario

    def _base_user(self, user_id: int) -> Dict[str, Any]:
        return {
            "id": user_id,
            "is_bot": False,
            "first_name": f"User{user_id}",
            "username": f"load_user_{user_id}",
            "language_code": "ru",
        }

    def _create_message_update(self, user_id: int, text: str, is_command: bool = False) -> Update:
        message_id = next(self._message_ids)
        update_data = {
            "update_id": next(self._update_ids),
            "message": {
                "message_id": message_id,
                "date": int(time.time()),
                "chat": {"id": user_id, "type": "private", "first_name": f"User{user_id}"},
                "from": self._base_user(user_id),
                "text": text,
            },
        }
        if is_command:
            update_data["message"]["entities"] = [
                {"type": "bot_command", "offset": 0, "length": len(text)}
            ]
        return Update.de_json(update_data, self.bot)

    def _create_callback_update(self, user_id: int, data: str, message_text: str) -> Update:
        message_id = next(self._message_ids)
        update_data = {
            "update_id": next(self._update_ids),
            "callback_query": {
                "id": str(uuid4()),
                "from": self._base_user(user_id),
                "data": data,
                "chat_instance": str(uuid4()),
                "message": {
                    "message_id": message_id,
                    "date": int(time.time()),
                    "chat": {"id": user_id, "type": "private", "first_name": f"User{user_id}"},
                    "from": {
                        "id": 0,
                        "is_bot": True,
                        "first_name": "Bot",
                    },
                    "text": message_text,
                },
            },
        }
        return Update.de_json(update_data, self.bot)

    def build_flow(self, user_id: int) -> List[Update]:
        updates: List[Update] = []
        updates.append(self._create_message_update(user_id, "/start", is_command=True))

        valid = random.random() < self.valid_email_ratio
        valid_email = "stud0000286472@study.utmn.ru"
        email = valid_email if valid else f"invalid_{user_id}@example.com"
        updates.append(self._create_message_update(user_id, email))

        if not valid:
            return updates

        if self.scenario == "simple":
            updates.append(self._create_message_update(user_id, "Спасибо"))
            updates.append(self._create_message_update(user_id, "Помощь"))
            return updates

        if self.scenario == "text_storm":
            noise_pool = [
                "Хочу узнать больше",
                "Расскажи про мероприятия",
                "Есть ли что-то на выходных?",
                "Где посмотреть расписание",
                "Нужна помощь",
            ]
            for burst_index in range(10):
                payload = random.choice(noise_pool)
                updates.append(
                    self._create_message_update(
                        user_id,
                        f"{payload}! #{burst_index + 1}",
                    )
                )
            updates.append(self._create_message_update(user_id, "Помощь"))
            return updates

        if self.scenario == "menu_spam":
            menu_cycle = [
                ("my_recommendations", "Главное меню"),
                ("like_1", "Рекомендации"),
                ("show_other_events", "Рекомендации"),
                ("back_to_menu", "Рекомендации"),
                ("event_search", "Главное меню"),
                ("filter_all", "Поиск мероприятий"),
                ("search_next", "Результаты поиска"),
                ("back_to_menu", "Результаты поиска"),
            ]
            for _ in range(5):
                for data, message_text in menu_cycle:
                    updates.append(self._create_callback_update(user_id, data, message_text))
            updates.append(self._create_callback_update(user_id, "feedback", "Главное меню"))
            updates.append(self._create_message_update(user_id, "Бот, ты выдержишь нагрузку?"))
            updates.append(self._create_callback_update(user_id, "back_to_menu", "Обратная связь"))
            return updates

        if self.scenario == "feedback_loop":
            updates.append(self._create_callback_update(user_id, "feedback", "Главное меню"))
            for idx in range(5):
                updates.append(
                    self._create_message_update(
                        user_id,
                        f"stud0000286472@study.utmn.ru подтверждаю участие #{idx + 1}",
                    )
                )
            updates.append(self._create_callback_update(user_id, "back_to_menu", "Обратная связь"))
            updates.append(self._create_message_update(user_id, "Помощь"))
            return updates

        updates.extend(
            [
                self._create_callback_update(user_id, "my_recommendations", "Главное меню"),
                self._create_callback_update(user_id, "like_1", "Рекомендации"),
                self._create_callback_update(user_id, "show_other_events", "Рекомендации"),
                self._create_callback_update(user_id, "back_to_menu", "Рекомендации"),
                self._create_callback_update(user_id, "event_search", "Главное меню"),
                self._create_callback_update(user_id, "filter_all", "Поиск мероприятий"),
                self._create_callback_update(user_id, "search_next", "Результаты поиска"),
                self._create_callback_update(user_id, "back_to_menu", "Результаты поиска"),
                self._create_callback_update(user_id, "feedback", "Главное меню"),
                self._create_message_update(user_id, "Отличный бот!"),
                self._create_callback_update(user_id, "back_to_menu", "Обратная связь"),
            ]
        )
        return updates


def _extract_chat_id(update: Update) -> Optional[int]:
    if update.message:
        return update.message.chat.id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.chat.id
    if update.edited_message:
        return update.edited_message.chat.id
    if update.channel_post:
        return update.channel_post.chat.id
    return None


async def process_update(
    application,
    update: Update,
    metrics: LoadTestMetrics,
    semaphore: asyncio.Semaphore,
    delay: float,
    rate_limiter: Optional[LiveRateLimiter],
    max_retries: int,
) -> None:  # type: ignore[no-untyped-def]
    async with semaphore:
        if delay:
            await asyncio.sleep(delay)
        attempts = 0
        total_duration = 0.0
        logger = logging.getLogger(__name__)
        while True:
            chat_id = _extract_chat_id(update)
            if rate_limiter is not None:
                await rate_limiter.throttle(chat_id)

            start = time.perf_counter()
            try:
                await application.process_update(update)
                total_duration += time.perf_counter() - start
            except RetryAfter as exc:  # pragma: no cover - зависит от внешнего API
                total_duration += time.perf_counter() - start
                attempts += 1
                logger.warning("Получен RetryAfter на %.2f c для chat_id=%s", exc.retry_after, chat_id)
                if attempts >= max_retries:
                    metrics.record(update, total_duration, exc)
                    break
                await asyncio.sleep(exc.retry_after)
                continue
            except (TimedOut, NetworkError) as exc:  # pragma: no cover - зависит от сети
                total_duration += time.perf_counter() - start
                attempts += 1
                if attempts >= max_retries:
                    metrics.record(update, total_duration, exc)
                    logger.warning("Достигнут предел повторов после ошибки %s", type(exc).__name__)
                    break
                backoff = min(0.5 * (2 ** (attempts - 1)), 5.0)
                logger.warning(
                    "Ошибка %s при обработке обновления, повтор через %.2f c (попытка %s/%s)",
                    type(exc).__name__,
                    backoff,
                    attempts,
                    max_retries,
                )
                await asyncio.sleep(backoff)
                continue
            except Exception as exc:  # pragma: no cover - логирование ошибок
                total_duration += time.perf_counter() - start
                metrics.record(update, total_duration, exc)
                logger.exception("Ошибка обработки обновления")
                break
            else:
                metrics.record(update, total_duration)
                break


async def _auto_discover_chat_ids(
    bot,
    limit: int,
    logger: logging.Logger,
) -> List[int]:  # type: ignore[no-untyped-def]
    """Получает последние обновления и извлекает ``chat_id``.

    Перед запуском пользователь должен отправить любое сообщение боту, чтобы
    обновления появились в очереди ``getUpdates``. Функция считывает не более
    ``limit`` событий, извлекает идентификаторы чатов и подтверждает их
    обработку запросом с ``offset``.
    """

    try:
        updates = await bot.get_updates(limit=limit, timeout=0)  # type: ignore[attr-defined]
    except Exception as exc:  # pragma: no cover - защитное логирование
        logger.error("Не удалось получить обновления через Bot API: %s", exc)
        raise

    chat_ids: Set[int] = set()
    for update in updates:
        if update.message:
            chat_ids.add(update.message.chat.id)
        elif update.edited_message:
            chat_ids.add(update.edited_message.chat.id)
        elif update.callback_query and update.callback_query.message:
            chat_ids.add(update.callback_query.message.chat.id)
        elif update.channel_post:
            chat_ids.add(update.channel_post.chat.id)
        elif update.my_chat_member:
            chat_ids.add(update.my_chat_member.chat.id)
        elif update.chat_member:
            chat_ids.add(update.chat_member.chat.id)

    if updates:
        # Подтверждаем получение, чтобы Bot API не возвращал те же обновления снова.
        last_update_id = updates[-1].update_id
        await bot.get_updates(offset=last_update_id + 1, timeout=0)  # type: ignore[attr-defined]

    discovered = sorted(chat_ids)
    if discovered:
        logger.info("Автоматически обнаружены chat_id: %s", ", ".join(map(str, discovered)))
    else:
        logger.warning(
            "Не удалось автоматически обнаружить chat_id. Отправьте сообщение боту и повторите попытку."
        )
    return discovered


async def run_load_test(args: argparse.Namespace) -> LoadTestMetrics:
    logger = logging.getLogger(__name__)
    if args.seed is not None:
        random.seed(args.seed)
        logger.info("Используется фиксированный seed генератора случайных чисел: %s", args.seed)
    if args.mode == "synthetic":
        request = FakeBotAPIRequest(artificial_delay=args.transport_delay)
    else:
        request = None
        if args.transport_delay:
            logger.warning("Игнорируем transport-delay в режиме live")
    application = build_application(bot_token=args.token, request=request)
    await application.initialize()

    metrics = LoadTestMetrics()
    global CURRENT_METRICS
    CURRENT_METRICS = metrics
    if args.mode == "live" and args.scenario in SCENARIOS_REQUIRING_CALLBACKS:
        fallback_scenario = "text_storm"
        logger.warning(
            "Сценарий '%s' содержит callback-запросы, которые невалидны для live-режима. "
            "Переключаемся на '%s'.",
            args.scenario,
            fallback_scenario,
        )
        args.scenario = fallback_scenario
    scenario_factory = ScenarioFactory(application.bot, args.valid_email_ratio, args.scenario)
    semaphore = asyncio.Semaphore(args.concurrency)
    rate_limiter: Optional[LiveRateLimiter] = None
    if args.mode == "live":
        rate_limiter = LiveRateLimiter(args.live_global_rate, args.live_chat_rate)

    chat_ids: List[int] = []
    if args.chat_ids:
        try:
            chat_ids.extend(
                int(value.strip()) for value in args.chat_ids.split(",") if value.strip()
            )
        except ValueError as exc:
            raise ValueError(
                "Некорректный формат chat-ids. Используйте числа через запятую."
            ) from exc
    if args.mode == "live" and args.auto_discover_chat_ids:
        discovered = await _auto_discover_chat_ids(application.bot, args.discover_limit, logger)
        for chat_id in discovered:
            if chat_id not in chat_ids:
                chat_ids.append(chat_id)
    if args.mode == "live" and not chat_ids:
        raise ValueError(
            "Для режима live необходимо указать хотя бы один chat-id через --chat-ids "
            "или включить автообнаружение --auto-discover-chat-ids"
        )
    chat_ids = sorted(set(chat_ids))

    stop_event = asyncio.Event()
    min_duration_reached = asyncio.Event()

    # Попытка корректно завершить тест по сигналу SIGINT (Unix)
    loop = asyncio.get_running_loop()
    try:
        loop.add_signal_handler(signal.SIGINT, stop_event.set)
    except (NotImplementedError, RuntimeError):  # pragma: no cover - Windows/embedded
        pass

    min_duration = max(0.0, float(getattr(args, "min_duration", 0.0)))

    async def duration_guard() -> None:
        if min_duration <= 0:
            return
        try:
            await asyncio.sleep(min_duration)
        except asyncio.CancelledError:  # pragma: no cover - отмена при завершении теста
            return
        logger.info("Минимальная длительность %.2f с достигнута, разрешаем завершение", min_duration)
        min_duration_reached.set()
        stop_event.set()

    async def run_for_user(user_id: int) -> None:
        actual_user_id = user_id
        if chat_ids:
            actual_user_id = chat_ids[(user_id - 1) % len(chat_ids)]
        iterations_done = 0
        while True:
            updates = scenario_factory.build_flow(actual_user_id)
            for update in updates:
                await process_update(
                    application,
                    update,
                    metrics,
                    semaphore,
                    args.inter_update_delay,
                    rate_limiter,
                    args.max_retries,
                )
            iterations_done += 1
            if min_duration <= 0 and iterations_done >= args.iterations:
                break
            if stop_event.is_set():
                if not min_duration_reached.is_set() or iterations_done >= args.iterations:
                    break

    logger.info(
        "Запуск нагрузочного теста: users=%s iterations=%s concurrency=%s",
        args.users,
        args.iterations,
        args.concurrency,
    )

    duration_task = asyncio.create_task(duration_guard())
    tasks = [asyncio.create_task(run_for_user(user_id)) for user_id in range(1, args.users + 1)]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:  # pragma: no cover - отмена при Ctrl+C
        stop_event.set()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
    finally:
        duration_task.cancel()
        await asyncio.gather(duration_task, return_exceptions=True)
        metrics.finish()
        try:
            await application.shutdown()
        except Exception as exc:  # pragma: no cover - защитное логирование
            logger.warning("Не удалось корректно остановить приложение: %s", exc)

    logger.info("Нагрузочное тестирование завершено")
    logger.info("Сводка: %s", json.dumps(metrics.summary(), ensure_ascii=False))
    return metrics


def configure_logging(log_path: Path, log_level: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Нагрузочное тестирование телеграм-бота")
    parser.add_argument("--users", type=int, default=50, help="Количество виртуальных пользователей")
    parser.add_argument("--iterations", type=int, default=5, help="Сколько раз каждый пользователь повторяет сценарий")
    parser.add_argument(
        "--concurrency", type=int, default=20, help="Максимум одновременно обрабатываемых обновлений"
    )
    parser.add_argument(
        "--valid-email-ratio",
        type=float,
        default=0.8,
        help="Доля пользователей, вводящих корректный email",
    )
    parser.add_argument(
        "--inter-update-delay",
        type=float,
        default=0.0,
        help="Задержка (сек) между обновлениями для более реалистичного сценария",
    )
    parser.add_argument(
        "--transport-delay",
        type=float,
        default=0.0,
        help="Искусственная задержка в поддельном транспортном слое Bot API (только synthetic)",
    )
    parser.add_argument("--log-file", type=Path, default=Path("logs/load_test.log"))
    parser.add_argument(
        "--metrics-file", type=Path, default=Path("logs/load_test_metrics.json"), help="Путь к файлу со сводкой"
    )
    parser.add_argument(
        "--raw-metrics-file",
        type=Path,
        default=None,
        help="Если указан, сохраняет сырые метрики задержек в CSV",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("BOT_TOKEN", "TEST:TOKEN"),
        help="Токен для инициализации бота",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO", help="Уровень логирования (DEBUG, INFO, WARNING, ERROR)"
    )
    parser.add_argument("--seed", type=int, default=None, help="Seed для генератора случайных чисел")
    parser.add_argument(
        "--mode",
        choices=["synthetic", "live"],
        default="synthetic",
        help="Режим тестирования: synthetic (in-memory) или live (реальный Bot API)",
    )
    parser.add_argument(
        "--scenario",
        choices=["full", "simple", "text_storm", "menu_spam", "feedback_loop"],
        default="full",
        help="Тип пользовательского сценария",
    )
    parser.add_argument(
        "--profile",
        choices=["single", "stress", "spike", "soak"],
        default="single",
        help="Преднастроенный профиль нагрузки (single, stress, spike, soak)",
    )
    parser.add_argument(
        "--chat-ids",
        type=str,
        default=None,
        help="Список chat_id через запятую для live-режима",
    )
    parser.add_argument(
        "--auto-discover-chat-ids",
        action="store_true",
        help="Попытаться автоматически найти chat_id через Bot API (live-режим)",
    )
    parser.add_argument(
        "--discover-limit",
        type=int,
        default=20,
        help="Максимальное число обновлений для автообнаружения chat_id",
    )
    parser.add_argument(
        "--min-duration",
        type=float,
        default=300.0,
        help="Минимальная длительность теста в секундах до автоматического завершения",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Максимальное число повторов при ошибках Bot API",
    )
    parser.add_argument(
        "--live-global-rate",
        type=float,
        default=25.0,
        help="Глобальный лимит запросов в секунду для live-режима (0 — без ограничения)",
    )
    parser.add_argument(
        "--live-chat-rate",
        type=float,
        default=1.0,
        help="Лимит запросов в секунду на один чат для live-режима (0 — без ограничения)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file, args.log_level)

    phases = build_profile_phases(args)
    multi_phase = len(phases) > 1
    logger = logging.getLogger(__name__)
    global CURRENT_METRICS
    aggregated: List[Dict[str, Any]] = []
    phase_metrics_path: Optional[Path]
    phase_raw_path: Optional[Path]

    for phase in phases:
        requested_scenario = phase.scenario if phase.scenario is not None else args.scenario
        phase_args = phase.apply(args)
        logger.info("=== Фаза профиля %s ===", phase.label)
        logger.info(
            "Параметры фазы: mode=%s users=%s iterations=%s concurrency=%s scenario=%s inter_update_delay=%.3f valid_email_ratio=%.2f",
            phase_args.mode,
            phase_args.users,
            phase_args.iterations,
            phase_args.concurrency,
            phase_args.scenario,
            phase_args.inter_update_delay,
            phase_args.valid_email_ratio,
        )

        phase_metrics_path = (
            _suffix_path(args.metrics_file, phase.label) if multi_phase else args.metrics_file
        )
        phase_raw_path = None
        if args.raw_metrics_file:
            phase_raw_path = (
                _suffix_path(args.raw_metrics_file, phase.label)
                if multi_phase
                else args.raw_metrics_file
            )

        try:
            metrics = asyncio.run(run_load_test(phase_args))
        except KeyboardInterrupt:
            logger.warning("Фаза %s прервана пользователем", phase.label)
            metrics = CURRENT_METRICS or LoadTestMetrics()
            metrics.finish()
            summary = metrics.summary()
            metrics.dump(phase_metrics_path, phase_raw_path)
            aggregated.append(
                {
                    "label": phase.label,
                    "mode": phase_args.mode,
                    "users": phase_args.users,
                    "iterations": phase_args.iterations,
                    "concurrency": phase_args.concurrency,
                    "inter_update_delay": phase_args.inter_update_delay,
                    "valid_email_ratio": phase_args.valid_email_ratio,
                    "scenario": phase_args.scenario,
                    "requested_scenario": requested_scenario,
                    "transport_delay": getattr(phase_args, "transport_delay", None),
                    "summary": summary,
                    "metrics_file": str(phase_metrics_path),
                    "raw_metrics_file": str(phase_raw_path) if phase_raw_path else None,
                }
            )
            CURRENT_METRICS = None
            break
        else:
            summary = metrics.summary()
            metrics.dump(phase_metrics_path, phase_raw_path)

            aggregated.append(
                {
                    "label": phase.label,
                    "mode": phase_args.mode,
                    "users": phase_args.users,
                    "iterations": phase_args.iterations,
                    "concurrency": phase_args.concurrency,
                    "inter_update_delay": phase_args.inter_update_delay,
                    "valid_email_ratio": phase_args.valid_email_ratio,
                    "scenario": phase_args.scenario,
                    "requested_scenario": requested_scenario,
                    "transport_delay": getattr(phase_args, "transport_delay", None),
                    "summary": summary,
                    "metrics_file": str(phase_metrics_path),
                    "raw_metrics_file": str(phase_raw_path) if phase_raw_path else None,
                }
            )
            CURRENT_METRICS = None

    if multi_phase:
        aggregate_path = args.metrics_file
        aggregate_path.parent.mkdir(parents=True, exist_ok=True)
        with aggregate_path.open("w", encoding="utf-8") as fp:
            json.dump(
                {
                    "profile": args.profile,
                    "phases": aggregated,
                },
                fp,
                ensure_ascii=False,
                indent=2,
            )



if __name__ == "__main__":
    main()
