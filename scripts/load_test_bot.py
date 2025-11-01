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
import statistics
import sys
import time
from collections import defaultdict
from dataclasses import dataclass, field
from itertools import count
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import uuid4

from dotenv import load_dotenv
from telegram import Update
from telegram.request import BaseRequest, RequestData

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()
os.environ.setdefault("BOT_TOKEN", "TEST:TOKEN")

from src.bot.main import build_application


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
        self.total_updates += 1
        self.latencies.append(duration)
        update_type = "callback" if update.callback_query else "message" if update.message else "other"
        self.per_type_latencies[update_type].append(duration)
        self.latency_records.append((update_type, duration))

        if exc is not None:
            self.errors.append(f"{type(exc).__name__}: {exc}")

    def finish(self) -> None:
        self.end_ts = time.perf_counter()

    @property
    def duration(self) -> float:
        return max(self.end_ts - self.start_ts, 0.0)

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
        email = (
            f"stud0000{user_id:06d}@study.utmn.ru"
            if valid
            else f"invalid_{user_id}@example.com"
        )
        updates.append(self._create_message_update(user_id, email))

        if not valid:
            return updates

        if self.scenario == "simple":
            updates.append(self._create_message_update(user_id, "Спасибо"))
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


async def process_update(
    application,
    update: Update,
    metrics: LoadTestMetrics,
    semaphore: asyncio.Semaphore,
    delay: float,
) -> None:  # type: ignore[no-untyped-def]
    async with semaphore:
        if delay:
            await asyncio.sleep(delay)
        start = time.perf_counter()
        try:
            await application.process_update(update)
            duration = time.perf_counter() - start
            metrics.record(update, duration)
        except Exception as exc:  # pragma: no cover - логирование ошибок
            duration = time.perf_counter() - start
            metrics.record(update, duration, exc)
            logging.getLogger(__name__).exception("Ошибка обработки обновления")


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
    if args.mode == "live" and args.scenario == "full":
        logger.warning(
            "Сценарий 'full' содержит callback-запросы, которые невалидны для live-режима. "
            "Переключаемся на 'simple'."
        )
        args.scenario = "simple"
    scenario_factory = ScenarioFactory(application.bot, args.valid_email_ratio, args.scenario)
    semaphore = asyncio.Semaphore(args.concurrency)

    chat_ids: Optional[List[int]] = None
    if args.chat_ids:
        try:
            chat_ids = [int(value.strip()) for value in args.chat_ids.split(",") if value.strip()]
        except ValueError as exc:
            raise ValueError(
                "Некорректный формат chat-ids. Используйте числа через запятую."
            ) from exc
        if not chat_ids:
            raise ValueError("Список chat-ids пуст")
    elif args.mode == "live":
        raise ValueError("Для режима live необходимо указать хотя бы один chat-id")

    async def run_for_user(user_id: int) -> None:
        actual_user_id = user_id
        if chat_ids:
            actual_user_id = chat_ids[(user_id - 1) % len(chat_ids)]
        for _ in range(args.iterations):
            updates = scenario_factory.build_flow(actual_user_id)
            for update in updates:
                await process_update(application, update, metrics, semaphore, args.inter_update_delay)

    logger.info(
        "Запуск нагрузочного теста: users=%s iterations=%s concurrency=%s",
        args.users,
        args.iterations,
        args.concurrency,
    )

    tasks = [asyncio.create_task(run_for_user(user_id)) for user_id in range(1, args.users + 1)]
    await asyncio.gather(*tasks)

    metrics.finish()
    await application.shutdown()
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
        choices=["full", "simple"],
        default="full",
        help="Тип пользовательского сценария",
    )
    parser.add_argument(
        "--chat-ids",
        type=str,
        default=None,
        help="Список chat_id через запятую для live-режима",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging(args.log_file, args.log_level)

    metrics = asyncio.run(run_load_test(args))
    metrics.dump(args.metrics_file, args.raw_metrics_file)


if __name__ == "__main__":
    main()
