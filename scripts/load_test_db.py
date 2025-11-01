"""Нагрузочное тестирование Supabase/PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import random
import signal
import statistics
import sys
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError


_SESSION_FACTORY = None
_FEEDBACK_CRUD = None
_RECOMMENDATIONS_CRUD = None
_STUDENTS_CRUD = None
_FEEDBACK_MODEL = None
_STUDENTS_MODEL = None
_EVENTS_MODEL = None


def ensure_db_modules():
    global _SESSION_FACTORY, _FEEDBACK_CRUD, _RECOMMENDATIONS_CRUD, _STUDENTS_CRUD
    global _FEEDBACK_MODEL, _STUDENTS_MODEL, _EVENTS_MODEL

    if _SESSION_FACTORY is None:
        from src.core.database.connection import SessionLocal as _SessionLocal  # type: ignore
        from src.core.database.models import Feedback as _Feedback
        from src.core.database.models import Students as _Students
        from src.core.database.models import Events as _Events
        from src.core.database.crud import feedback as _feedback_crud
        from src.core.database.crud import recommendations as _recommendations_crud
        from src.core.database.crud import students as _students_crud

        _SESSION_FACTORY = _SessionLocal
        _FEEDBACK_CRUD = _feedback_crud
        _RECOMMENDATIONS_CRUD = _recommendations_crud
        _STUDENTS_CRUD = _students_crud
        _FEEDBACK_MODEL = _Feedback
        _STUDENTS_MODEL = _Students
        _EVENTS_MODEL = _Events

    return (
        _SESSION_FACTORY,
        _FEEDBACK_CRUD,
        _RECOMMENDATIONS_CRUD,
        _STUDENTS_CRUD,
        _FEEDBACK_MODEL,
        _STUDENTS_MODEL,
        _EVENTS_MODEL,
    )


# ---------------------------------------------------------------------------
# Константы и вспомогательные структуры
# ---------------------------------------------------------------------------


TRANSIENT_ERRORS = (OperationalError, InterfaceError)


class SkipOperation(Exception):
    """Исключение, сигнализирующее об отсутствии данных для операции."""


@dataclass
class StudentRef:
    id: Any
    participant_id: str


@dataclass
class DataCache:
    students: list[StudentRef]
    event_ids: list[Any]
    feedback_ids: list[int]

    def ensure_ready(self) -> None:
        if not self.students:
            raise RuntimeError(
                "В таблице students нет записей — нагрузочный тест невозможен"
            )
        if not self.event_ids:
            raise RuntimeError(
                "В таблице events нет записей — нагрузочный тест невозможен"
            )

    def random_student(self, rng: random.Random) -> StudentRef:
        return rng.choice(self.students)

    def random_student_id(self, rng: random.Random) -> Any:
        return self.random_student(rng).id

    def random_participant(self, rng: random.Random) -> str:
        return self.random_student(rng).participant_id

    def random_event_id(self, rng: random.Random) -> Any:
        return rng.choice(self.event_ids)

    def random_feedback_id(self, rng: random.Random) -> int:
        if not self.feedback_ids:
            raise SkipOperation("Нет отзывов для обновления/чтения")
        return rng.choice(self.feedback_ids)

    def add_feedback_id(self, feedback_id: int) -> None:
        self.feedback_ids.append(feedback_id)


@dataclass
class SharedState:
    cache: DataCache
    cleanup: bool
    created_feedback_ids: list[int] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def register_feedback(self, feedback_id: int, *, is_new: bool) -> None:
        with self.lock:
            if is_new:
                self.created_feedback_ids.append(feedback_id)
            self.cache.add_feedback_id(feedback_id)


@dataclass
class OperationSpec:
    name: str
    op_type: str
    weight: int
    func: Callable[[Any, SharedState, random.Random], Any]


@dataclass
class OperationResult:
    name: str
    op_type: str
    started_at: float
    ended_at: float
    attempts: int
    success: bool
    skipped: bool
    error: str | None

    @property
    def latency(self) -> float:
        return self.ended_at - self.started_at


class OperationPicker:
    def __init__(self, operations: Sequence[OperationSpec]):
        self.operations = list(operations)
        if not self.operations:
            raise ValueError("Не заданы операции для профиля нагрузки")
        self.cumulative: list[tuple[float, OperationSpec]] = []
        total = 0.0
        for op in self.operations:
            if op.weight <= 0:
                continue
            total += op.weight
            self.cumulative.append((total, op))
        if not self.cumulative:
            raise ValueError("Все операции имеют нулевой вес")
        self.total_weight = total

    def choose(self, rng: random.Random) -> OperationSpec:
        value = rng.random() * self.total_weight
        for threshold, op in self.cumulative:
            if value <= threshold:
                return op
        return self.cumulative[-1][1]


class LoadTestMetrics:
    def __init__(self) -> None:
        self._results: list[OperationResult] = []

    def add(self, result: OperationResult) -> None:
        self._results.append(result)

    @property
    def results(self) -> list[OperationResult]:
        return self._results

    def summary(self) -> dict[str, Any]:
        if not self._results:
            return {
                "total_operations": 0,
                "success": 0,
                "skipped": 0,
                "errors": 0,
                "duration_sec": 0.0,
                "throughput_rps": 0.0,
                "latency": {},
                "per_operation": {},
            }

        total = len(self._results)
        success = sum(1 for r in self._results if r.success)
        skipped = sum(1 for r in self._results if r.skipped)
        errors = total - success
        first = min(r.started_at for r in self._results)
        last = max(r.ended_at for r in self._results)
        duration = max(last - first, 1e-9)
        throughput = total / duration
        latency_stats = self._compute_latency(self._results)
        per_operation: dict[str, Any] = {}
        groups: dict[str, list[OperationResult]] = defaultdict(list)
        for result in self._results:
            groups[result.name].append(result)
        for name, values in groups.items():
            per_operation[name] = {
                "count": len(values),
                "success": sum(1 for r in values if r.success),
                "skipped": sum(1 for r in values if r.skipped),
                "errors": sum(1 for r in values if not r.success),
                "latency": self._compute_latency(values),
            }

        return {
            "total_operations": total,
            "success": success,
            "skipped": skipped,
            "errors": errors,
            "duration_sec": duration,
            "throughput_rps": throughput,
            "latency": latency_stats,
            "per_operation": per_operation,
        }

    def _compute_latency(self, results: Iterable[OperationResult]) -> dict[str, float]:
        values = [r.latency for r in results if not r.skipped]
        if not values:
            return {}
        values.sort()
        return {
            "avg": sum(values) / len(values),
            "median": statistics.median(values),
            "p95": percentile(values, 95),
            "p99": percentile(values, 99),
            "min": values[0],
            "max": values[-1],
        }


# ---------------------------------------------------------------------------
# Утилиты
# ---------------------------------------------------------------------------


def percentile(values: Sequence[float], target: float) -> float:
    if not values:
        return math.nan
    if target <= 0:
        return values[0]
    if target >= 100:
        return values[-1]
    rank = (len(values) - 1) * (target / 100)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return values[int(rank)]
    weight = rank - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def configure_logging(log_dir: Path, level: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = log_dir / f"db_load_{timestamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    log_file = run_dir / "run.log"

    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    logging.getLogger(__name__).info("Логи сохраняются в %s", log_file)
    return run_dir


def load_cache(prefetch: int, logger: logging.Logger) -> DataCache:
    session_factory, _, _, _, feedback_model, students_model, events_model = ensure_db_modules()
    if session_factory is None:
        raise RuntimeError("Не удалось инициализировать соединение с базой данных")

    with session_factory() as session:
        student_rows = session.execute(
            select(students_model.id, students_model.participant_id).limit(prefetch)
        ).all()
        event_rows = session.execute(select(events_model.id).limit(prefetch)).all()
        feedback_rows = session.execute(select(feedback_model.id).limit(prefetch)).all()

    students = [StudentRef(id=row[0], participant_id=row[1]) for row in student_rows]
    event_ids = [row[0] for row in event_rows]
    feedback_ids = [row[0] for row in feedback_rows]

    logger.info(
        "Предзагружено объектов: %d студентов, %d событий, %d отзывов",
        len(students),
        len(event_ids),
        len(feedback_ids),
    )

    cache = DataCache(students=students, event_ids=event_ids, feedback_ids=feedback_ids)
    cache.ensure_ready()
    return cache


def build_operations(profile: str, state: SharedState) -> list[OperationSpec]:
    base_ops = {
        "fetch_student": OperationSpec(
            name="fetch_student",
            op_type="read",
            weight=4,
            func=op_fetch_student,
        ),
        "fetch_recommendations": OperationSpec(
            name="fetch_recommendations",
            op_type="read",
            weight=4,
            func=op_fetch_recommendations,
        ),
        "fetch_events": OperationSpec(
            name="fetch_events",
            op_type="read",
            weight=3,
            func=op_fetch_events,
        ),
        "list_feedback": OperationSpec(
            name="list_feedback",
            op_type="read",
            weight=2,
            func=op_list_feedback,
        ),
        "create_feedback": OperationSpec(
            name="create_feedback",
            op_type="write",
            weight=2,
            func=op_create_feedback,
        ),
        "update_feedback": OperationSpec(
            name="update_feedback",
            op_type="write",
            weight=1,
            func=op_update_feedback,
        ),
    }

    profiles: dict[str, dict[str, int]] = {
        "read-heavy": {
            "fetch_student": 6,
            "fetch_recommendations": 6,
            "fetch_events": 4,
            "list_feedback": 2,
            "create_feedback": 1,
            "update_feedback": 1,
        },
        "write-heavy": {
            "fetch_student": 3,
            "fetch_recommendations": 2,
            "fetch_events": 2,
            "list_feedback": 1,
            "create_feedback": 4,
            "update_feedback": 3,
        },
        "mixed": {
            "fetch_student": 4,
            "fetch_recommendations": 4,
            "fetch_events": 3,
            "list_feedback": 2,
            "create_feedback": 3,
            "update_feedback": 2,
        },
    }

    if profile not in profiles:
        raise ValueError(
            f"Неизвестный профиль '{profile}'. Доступные значения: {', '.join(profiles)}"
        )

    overrides = profiles[profile]
    operations: list[OperationSpec] = []
    for key, base in base_ops.items():
        weight = overrides.get(key, base.weight)
        operations.append(
            OperationSpec(
                name=base.name,
                op_type=base.op_type,
                weight=weight,
                func=base.func,
            )
        )
    return operations


# ---------------------------------------------------------------------------
# Операции
# ---------------------------------------------------------------------------


COMMENT_TEMPLATES = [
    "Очень понравился подбор мероприятий!",
    "Хочу больше онлайн-событий по аналитике.",
    "Спасибо за рекомендации, всё актуально.",
    "Есть идеи по улучшению интерфейса.",
    "Добавьте, пожалуйста, мероприятия по дизайну.",
]


def run_with_session(func: Callable[[Any, SharedState, random.Random, Any], Any], state: SharedState, rng: random.Random, *extra: Any) -> Any:
    session_factory, *_ = ensure_db_modules()
    if session_factory is None:
        raise RuntimeError("Сессия базы данных не инициализирована")
    with session_factory() as session:
        return func(session, state, rng, *extra)


def op_fetch_student(session, state: SharedState, rng: random.Random):
    _, _, _, students_module, _, _, _ = ensure_db_modules()
    participant = state.cache.random_participant(rng)
    students_module.get_student_by_participant_id(session, participant)


def op_fetch_recommendations(session, state: SharedState, rng: random.Random):
    _, _, recommendations_module, _, _, _, _ = ensure_db_modules()
    student_id = state.cache.random_student_id(rng)
    recommendations_module.get_recommendations_for_student(session, student_id, limit=20)


def op_fetch_events(session, state: SharedState, rng: random.Random):
    _, _, _, _, _, _, events_model = ensure_db_modules()
    limit = rng.randint(10, 50)
    session.execute(select(events_model.id, events_model.title).limit(limit)).all()


def op_list_feedback(session, state: SharedState, rng: random.Random):
    _, feedback_module, _, _, _, _, _ = ensure_db_modules()
    try:
        student_id = state.cache.random_student_id(rng)
    except IndexError:
        raise SkipOperation("Нет студентов для чтения отзывов") from None
    feedback_module.get_feedbacks_by_student(session, student_id)


def op_create_feedback(session, state: SharedState, rng: random.Random):
    _, feedback_module, _, _, _, _, _ = ensure_db_modules()
    student_id = state.cache.random_student_id(rng)
    rating = rng.randint(3, 5)
    comment = rng.choice(COMMENT_TEMPLATES)
    feedback_obj = feedback_module.create_feedback(
        session,
        student_id=student_id,
        rating=rating,
        comment=comment,
    )
    state.register_feedback(feedback_obj.id, is_new=True)


def op_update_feedback(session, state: SharedState, rng: random.Random):
    _, feedback_module, _, _, _, _, _ = ensure_db_modules()
    feedback_id = state.cache.random_feedback_id(rng)
    new_rating = rng.randint(1, 5)
    new_comment = rng.choice(COMMENT_TEMPLATES)
    feedback_module.update_feedback(
        session,
        feedback_id=feedback_id,
        rating=new_rating,
        comment=new_comment,
    )


# ---------------------------------------------------------------------------
# Основная логика
# ---------------------------------------------------------------------------


async def worker(
    name: str,
    picker: OperationPicker,
    state: SharedState,
    results: asyncio.Queue,
    stop_event: asyncio.Event,
    end_time: float,
    max_retries: int,
    rng_seed: float,
    backoff_base: float,
) -> None:
    logger = logging.getLogger(f"worker.{name}")
    rng = random.Random(rng_seed)

    while not stop_event.is_set():
        now = time.monotonic()
        if now >= end_time:
            break

        spec = picker.choose(rng)
        started_at = time.monotonic()
        wall_start = time.time()
        attempts = 0
        error: str | None = None
        success = False
        skipped = False

        while attempts <= max_retries:
            attempts += 1
            try:
                await asyncio.to_thread(run_with_session, spec.func, state, rng)
                success = True
                break
            except SkipOperation as exc:
                skipped = True
                error = str(exc)
                success = True
                break
            except TRANSIENT_ERRORS as exc:
                error = str(exc)
                if attempts > max_retries:
                    logger.warning("Операция %s исчерпала повторы: %s", spec.name, exc)
                    break
                sleep_for = backoff_base * attempts
                logger.debug(
                    "Повтор операции %s через %.2f с после ошибки: %s",
                    spec.name,
                    sleep_for,
                    exc,
                )
                await asyncio.sleep(sleep_for)
            except SQLAlchemyError as exc:
                error = str(exc)
                logger.error("Ошибка SQLAlchemy в операции %s: %s", spec.name, exc)
                break
            except Exception as exc:  # noqa: BLE001
                error = str(exc)
                logger.exception("Непредвиденная ошибка в операции %s", spec.name)
                break

        ended_at = time.monotonic()
        result_error = error if error else None
        result = OperationResult(
            name=spec.name,
            op_type=spec.op_type,
            started_at=wall_start,
            ended_at=wall_start + (ended_at - started_at),
            attempts=attempts,
            success=success,
            skipped=skipped,
            error=result_error,
        )
        await results.put(result)

    logger.info("Завершение работы")


async def consume_results(queue: asyncio.Queue, metrics: LoadTestMetrics, stop_event: asyncio.Event) -> None:
    while not (stop_event.is_set() and queue.empty()):
        try:
            result: OperationResult = await asyncio.wait_for(queue.get(), timeout=0.5)
        except asyncio.TimeoutError:
            continue
        metrics.add(result)
        queue.task_done()


def export_metrics(
    metrics: LoadTestMetrics,
    run_dir: Path,
    raw_path: Path | None,
    summary_path: Path | None,
    per_type_path: Path | None,
    timeline_path: Path | None,
    errors_path: Path | None,
) -> None:
    if raw_path is None:
        raw_path = run_dir / "operations.csv"
    if summary_path is None:
        summary_path = run_dir / "summary.json"
    if per_type_path is None:
        per_type_path = run_dir / "per_type.json"
    if timeline_path is None:
        timeline_path = run_dir / "timeline.ndjson"
    if errors_path is None:
        errors_path = run_dir / "errors.ndjson"

    raw_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    per_type_path.parent.mkdir(parents=True, exist_ok=True)
    timeline_path.parent.mkdir(parents=True, exist_ok=True)
    errors_path.parent.mkdir(parents=True, exist_ok=True)

    results = metrics.results
    fieldnames = [
        "started_at",
        "ended_at",
        "latency_ms",
        "operation",
        "type",
        "attempts",
        "success",
        "skipped",
        "error",
    ]
    with raw_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "started_at": datetime.fromtimestamp(result.started_at, tz=timezone.utc).isoformat(),
                    "ended_at": datetime.fromtimestamp(result.ended_at, tz=timezone.utc).isoformat(),
                    "latency_ms": (result.latency) * 1000,
                    "operation": result.name,
                    "type": result.op_type,
                    "attempts": result.attempts,
                    "success": int(result.success),
                    "skipped": int(result.skipped),
                    "error": result.error or "",
                }
            )

    summary = metrics.summary()
    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, ensure_ascii=False, indent=2)

    per_type: dict[str, Counter] = defaultdict(Counter)
    for result in results:
        per_type[result.op_type]["total"] += 1
        if result.success:
            per_type[result.op_type]["success"] += 1
        if result.skipped:
            per_type[result.op_type]["skipped"] += 1
        if not result.success:
            per_type[result.op_type]["errors"] += 1

    with per_type_path.open("w", encoding="utf-8") as file:
        json.dump({k: dict(v) for k, v in per_type.items()}, file, ensure_ascii=False, indent=2)

    with timeline_path.open("w", encoding="utf-8") as file:
        for result in sorted(results, key=lambda r: r.started_at):
            payload = {
                "time": datetime.fromtimestamp(result.started_at, tz=timezone.utc).isoformat(),
                "operation": result.name,
                "type": result.op_type,
                "latency_ms": result.latency * 1000,
                "attempts": result.attempts,
                "success": result.success,
                "skipped": result.skipped,
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")

    with errors_path.open("w", encoding="utf-8") as file:
        for result in results:
            if result.success and not result.error:
                continue
            payload = {
                "time": datetime.fromtimestamp(result.started_at, tz=timezone.utc).isoformat(),
                "operation": result.name,
                "error": result.error,
                "attempts": result.attempts,
            }
            file.write(json.dumps(payload, ensure_ascii=False) + "\n")


async def run_load_test(args: argparse.Namespace) -> tuple[LoadTestMetrics, SharedState]:
    logger = logging.getLogger("db_load_test")

    cache = load_cache(args.prefetch_limit, logger)
    state = SharedState(cache=cache, cleanup=not args.no_cleanup)

    operations = build_operations(args.profile, state)
    picker = OperationPicker(operations)

    duration = max(args.duration, 0)
    if duration <= 0 and not args.allow_short_runs:
        raise ValueError("Длительность должна быть положительной")

    if duration < args.min_duration and not args.allow_short_runs:
        logger.warning(
            "Запрошенная длительность %.2f с меньше минимального порога %.2f с — принудительно увеличиваем",
            duration,
            args.min_duration,
        )
        duration = args.min_duration

    start_time = time.monotonic()
    end_time = start_time + duration

    stop_event = asyncio.Event()
    results_queue: asyncio.Queue = asyncio.Queue()
    metrics = LoadTestMetrics()

    async def _handle_signal(signum, frame):  # noqa: D401
        logger.warning("Получен сигнал %s — корректное завершение", signum)
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop_event.set)
        except NotImplementedError:  # pragma: no cover
            signal.signal(sig, _handle_signal)  # type: ignore[arg-type]

    consumer_task = asyncio.create_task(consume_results(results_queue, metrics, stop_event))

    seeds = [random.random() if args.seed is None else random.Random(args.seed + i).random() for i in range(args.concurrency)]

    workers = [
        asyncio.create_task(
            worker(
                name=str(i),
                picker=picker,
                state=state,
                results=results_queue,
                stop_event=stop_event,
                end_time=end_time,
                max_retries=args.max_retries,
                rng_seed=seeds[i],
                backoff_base=args.backoff,
            )
        )
        for i in range(args.concurrency)
    ]

    try:
        await asyncio.gather(*workers)
    finally:
        stop_event.set()
        await consumer_task

    actual_duration = time.monotonic() - start_time
    if actual_duration < args.min_duration and not args.allow_short_runs:
        raise RuntimeError(
            f"Фактическая длительность {actual_duration:.2f} с меньше требуемых {args.min_duration:.2f} с"
        )

    logger.info("Выполнено операций: %d", len(metrics.results))
    return metrics, state


def cleanup_feedback(state: SharedState, logger: logging.Logger) -> None:
    if not state.cleanup:
        logger.info("Флаг очистки выключен, сохранено %d новых отзывов", len(state.created_feedback_ids))
        return
    if not state.created_feedback_ids:
        logger.info("Во время теста не создано новых отзывов")
        return

    session_factory, feedback_module, *_ = ensure_db_modules()
    if session_factory is None or feedback_module is None:
        logger.error("Не удалось инициализировать зависимости для очистки отзывов")
        return

    with session_factory() as session:
        for feedback_id in state.created_feedback_ids:
            try:
                feedback_module.delete_feedback(session, feedback_id)
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось удалить временный отзыв %s", feedback_id)
    logger.info("Удалено временных отзывов: %d", len(state.created_feedback_ids))


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Нагрузочное тестирование базы данных Supabase")
    parser.add_argument("--duration", type=float, default=600.0, help="Желаемая длительность теста, секунды")
    parser.add_argument("--min-duration", type=float, default=600.0, help="Минимально допустимая длительность теста")
    parser.add_argument("--allow-short-runs", action="store_true", help="Разрешить запуск короче минимального времени")
    parser.add_argument("--concurrency", type=int, default=16, help="Количество параллельных воркеров")
    parser.add_argument("--profile", choices=["read-heavy", "write-heavy", "mixed"], default="mixed", help="Профиль нагрузки")
    parser.add_argument("--prefetch-limit", type=int, default=2000, help="Сколько записей предзагружать из справочников")
    parser.add_argument("--max-retries", type=int, default=3, help="Сколько повторов выполнять при транзиентных ошибках")
    parser.add_argument("--backoff", type=float, default=0.5, help="Базовая задержка (сек) перед повтором транзиентной ошибки")
    parser.add_argument("--log-dir", default="logs/db", help="Каталог для логов и отчётов")
    parser.add_argument("--raw-metrics-file", help="Путь к CSV с покадровыми задержками")
    parser.add_argument("--summary-file", help="Путь к JSON с агрегированными метриками")
    parser.add_argument("--per-type-file", help="JSON со сводкой по типам операций")
    parser.add_argument("--timeline-file", help="NDJSON с временной шкалой операций")
    parser.add_argument("--errors-file", help="NDJSON с ошибками и повторами")
    parser.add_argument("--no-cleanup", action="store_true", help="Не удалять созданные во время теста отзывы")
    parser.add_argument("--seed", type=int, help="Фиксированный seed для генератора случайных чисел")
    parser.add_argument("--log-level", default=os.getenv("LOG_LEVEL", "INFO"), help="Уровень логирования")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    log_dir = Path(args.log_dir)
    run_dir = configure_logging(log_dir, args.log_level)
    logger = logging.getLogger("db_load_main")

    logger.info("Старт нагрузочного тестирования базы данных")
    logger.info("Используется профиль: %s, воркеров: %d, длительность: %.2f с", args.profile, args.concurrency, args.duration)

    try:
        metrics, state = asyncio.run(run_load_test(args))
    except KeyboardInterrupt:  # pragma: no cover
        logger.warning("Тест прерван пользователем")
        return
    except Exception as exc:  # noqa: BLE001
        logger.exception("Тест завершился ошибкой: %s", exc)
        raise
    else:
        logger.info("Нагрузочный тест завершён")
    finally:
        # Финальный логгер может писать даже если run_load_test упал
        pass

    export_metrics(
        metrics,
        run_dir,
        raw_path=Path(args.raw_metrics_file) if args.raw_metrics_file else None,
        summary_path=Path(args.summary_file) if args.summary_file else None,
        per_type_path=Path(args.per_type_file) if args.per_type_file else None,
        timeline_path=Path(args.timeline_file) if args.timeline_file else None,
        errors_path=Path(args.errors_file) if args.errors_file else None,
    )

    cleanup_feedback(state, logger)


if __name__ == "__main__":
    main()

