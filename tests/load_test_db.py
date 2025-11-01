
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
from uuid import uuid4

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select, update
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError


_MODULES: dict[str, Any] | None = None


def ensure_db_modules() -> dict[str, Any]:
    global _MODULES

    if _MODULES is None:
        from src.core.database.connection import SessionLocal as _SessionLocal  # type: ignore
        from src.core.database.crud import clusters as _clusters_crud
        from src.core.database.crud import directions as _directions_crud
        from src.core.database.crud import feedback as _feedback_crud
        from src.core.database.crud import recommendations as _recommendations_crud
        from src.core.database.crud import students as _students_crud
        from src.core.database.models import Clusters as _Clusters
        from src.core.database.models import Directions as _Directions
        from src.core.database.models import Directions as _Directions
        from src.core.database.models import Events as _Events
        from src.core.database.models import Feedback as _Feedback
        from src.core.database.models import Students as _Students

        _MODULES = {
            "session_factory": _SessionLocal,
            "feedback_crud": _feedback_crud,
            "recommendations_crud": _recommendations_crud,
            "students_crud": _students_crud,
            "clusters_crud": _clusters_crud,
            "directions_crud": _directions_crud,
            "feedback_model": _Feedback,
            "students_model": _Students,
            "events_model": _Events,
            "clusters_model": _Clusters,
            "directions_model": _Directions,
        }

    return _MODULES


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
    cluster_ids: list[Any]
    direction_ids: list[Any]
    direction_to_cluster: dict[Any, Any] = field(default_factory=dict)
    directions_by_cluster: dict[Any, list[Any]] = field(default_factory=lambda: defaultdict(list))

    def has_students(self) -> bool:
        return bool(self.students)

    def has_events(self) -> bool:
        return bool(self.event_ids)

    def has_clusters(self) -> bool:
        return bool(self.cluster_ids)

    def ensure_standard_data(self) -> None:
        if not self.has_students():
            raise RuntimeError(
                "В таблице students нет записей — профиль с рекомендациями недоступен"
            )
        if not self.has_events():
            raise RuntimeError(
                "В таблице events нет записей — профиль с рекомендациями недоступен"
            )

    def ensure_cluster_data(self) -> None:
        if not self.has_clusters():
            raise RuntimeError(
                "В таблице clusters нет записей — профиль для направлений недоступен"
            )

    def random_student(self, rng: random.Random) -> StudentRef:
        if not self.students:
            raise SkipOperation("Нет студентов для операции")
        return rng.choice(self.students)

    def random_student_id(self, rng: random.Random) -> Any:
        return self.random_student(rng).id

    def random_participant(self, rng: random.Random) -> str:
        return self.random_student(rng).participant_id

    def random_event_id(self, rng: random.Random) -> Any:
        if not self.event_ids:
            raise SkipOperation("Нет событий для операции")
        return rng.choice(self.event_ids)

    def random_feedback_id(self, rng: random.Random) -> int:
        if not self.feedback_ids:
            raise SkipOperation("Нет отзывов для обновления/чтения")
        return rng.choice(self.feedback_ids)

    def random_cluster_id(self, rng: random.Random) -> Any:
        if not self.cluster_ids:
            raise SkipOperation("Нет кластеров для операции")
        return rng.choice(self.cluster_ids)

    def random_direction_id(self, rng: random.Random) -> Any:
        if not self.direction_ids:
            raise SkipOperation("Нет направлений для операции")
        return rng.choice(self.direction_ids)

    def add_feedback_id(self, feedback_id: int) -> None:
        self.feedback_ids.append(feedback_id)

    def add_direction(self, direction_id: Any, cluster_id: Any) -> None:
        self.direction_ids.append(direction_id)
        self.direction_to_cluster[direction_id] = cluster_id
        if cluster_id is not None:
            self.directions_by_cluster.setdefault(cluster_id, []).append(direction_id)

    def remove_direction(self, direction_id: Any) -> None:
        if direction_id in self.direction_ids:
            self.direction_ids.remove(direction_id)
        cluster_id = self.direction_to_cluster.pop(direction_id, None)
        if cluster_id is not None:
            bucket = self.directions_by_cluster.get(cluster_id)
            if bucket and direction_id in bucket:
                bucket.remove(direction_id)
                if not bucket:
                    self.directions_by_cluster.pop(cluster_id, None)

    def update_direction_cluster(self, direction_id: Any, new_cluster: Any) -> None:
        old_cluster = self.direction_to_cluster.get(direction_id)
        if old_cluster is not None and old_cluster in self.directions_by_cluster:
            bucket = self.directions_by_cluster[old_cluster]
            if direction_id in bucket:
                bucket.remove(direction_id)
                if not bucket:
                    self.directions_by_cluster.pop(old_cluster, None)
        self.direction_to_cluster[direction_id] = new_cluster
        if new_cluster is not None:
            self.directions_by_cluster.setdefault(new_cluster, []).append(direction_id)


@dataclass
class SharedState:
    cache: DataCache
    cleanup: bool
    created_feedback_ids: list[int] = field(default_factory=list)
    created_direction_ids: list[Any] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock)

    def register_feedback(self, feedback_id: int, *, is_new: bool) -> None:
        with self.lock:
            if is_new:
                self.created_feedback_ids.append(feedback_id)
            self.cache.add_feedback_id(feedback_id)

    def register_direction(self, direction_id: Any, cluster_id: Any, *, is_new: bool) -> None:
        with self.lock:
            if is_new:
                self.created_direction_ids.append(direction_id)
            self.cache.add_direction(direction_id, cluster_id)

    def mark_direction_deleted(self, direction_id: Any) -> None:
        with self.lock:
            if direction_id in self.created_direction_ids:
                self.created_direction_ids.remove(direction_id)
            self.cache.remove_direction(direction_id)

    def update_direction_cluster(self, direction_id: Any, cluster_id: Any) -> None:
        with self.lock:
            self.cache.update_direction_cluster(direction_id, cluster_id)

    def pick_temp_direction(self, rng: random.Random) -> Any:
        with self.lock:
            if not self.created_direction_ids:
                raise SkipOperation("Нет временных направлений для операций")
            return rng.choice(self.created_direction_ids)


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
    modules = ensure_db_modules()
    session_factory = modules["session_factory"]
    feedback_model = modules["feedback_model"]
    students_model = modules["students_model"]
    events_model = modules["events_model"]
    clusters_model = modules["clusters_model"]
    directions_model = modules["directions_model"]
    if session_factory is None:
        raise RuntimeError("Не удалось инициализировать соединение с базой данных")

    with session_factory() as session:
        student_rows = session.execute(
            select(students_model.id, students_model.participant_id).limit(prefetch)
        ).all()
        event_rows = session.execute(select(events_model.id).limit(prefetch)).all()
        feedback_rows = session.execute(select(feedback_model.id).limit(prefetch)).all()
        cluster_rows = session.execute(select(clusters_model.id).limit(prefetch)).all()
        direction_rows = session.execute(
            select(directions_model.id, directions_model.cluster_id).limit(prefetch)
        ).all()

    students = [StudentRef(id=row[0], participant_id=row[1]) for row in student_rows]
    event_ids = [row[0] for row in event_rows]
    feedback_ids = [row[0] for row in feedback_rows]
    cluster_ids = [row[0] for row in cluster_rows]
    direction_ids = [row[0] for row in direction_rows]

    direction_to_cluster = {row[0]: row[1] for row in direction_rows}
    directions_by_cluster: dict[Any, list[Any]] = defaultdict(list)
    for direction_id, cluster_id in direction_to_cluster.items():
        if cluster_id is not None:
            directions_by_cluster[cluster_id].append(direction_id)

    logger.info(
        "Предзагружено объектов: %d студентов, %d событий, %d отзывов, %d кластеров, %d направлений",
        len(students),
        len(event_ids),
        len(feedback_ids),
        len(cluster_ids),
        len(direction_ids),
    )

    cache = DataCache(
        students=students,
        event_ids=event_ids,
        feedback_ids=feedback_ids,
        cluster_ids=cluster_ids,
        direction_ids=direction_ids,
        direction_to_cluster=direction_to_cluster,
        directions_by_cluster=directions_by_cluster,
    )
    return cache


def build_operations(profile: str, state: SharedState) -> list[OperationSpec]:
    rec_ops = {
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

    cluster_ops = {
        "list_clusters": OperationSpec(
            name="list_clusters",
            op_type="read",
            weight=4,
            func=op_list_clusters,
        ),
        "list_directions": OperationSpec(
            name="list_directions",
            op_type="read",
            weight=3,
            func=op_list_directions,
        ),
        "cluster_overview": OperationSpec(
            name="cluster_overview",
            op_type="read",
            weight=3,
            func=op_cluster_overview,
        ),
        "create_direction": OperationSpec(
            name="create_direction",
            op_type="write",
            weight=2,
            func=op_create_direction,
        ),
        "update_direction": OperationSpec(
            name="update_direction",
            op_type="write",
            weight=2,
            func=op_update_direction,
        ),
        "delete_direction": OperationSpec(
            name="delete_direction",
            op_type="write",
            weight=1,
            func=op_delete_direction,
        ),
        "reassign_direction": OperationSpec(
            name="reassign_direction",
            op_type="write",
            weight=1,
            func=op_reassign_direction,
        ),
    }

    rec_profiles: dict[str, dict[str, int]] = {
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
        "stress-test": {  # Добавьте новый профиль
            "fetch_student": 2,
            "fetch_recommendations": 2,
            "fetch_events": 1,
            "list_feedback": 1,
            "create_feedback": 8,  # Больше операций записи
            "update_feedback": 6,
        },
    }

    cluster_profiles: dict[str, dict[str, int]] = {
        "clusters-read": {
            "list_clusters": 6,
            "list_directions": 5,
            "cluster_overview": 4,
        },
        "clusters-write": {
            "list_clusters": 2,
            "create_direction": 5,
            "update_direction": 4,
            "delete_direction": 3,
            "reassign_direction": 3,
        },
        "clusters-mixed": {
            "list_clusters": 4,
            "list_directions": 4,
            "cluster_overview": 3,
            "create_direction": 3,
            "update_direction": 2,
            "delete_direction": 2,
            "reassign_direction": 2,
        },
    }

    if profile == "auto":
        if state.cache.has_students() and state.cache.has_events():
            profile = "mixed"
        elif state.cache.has_clusters():
            profile = "clusters-mixed"
        else:
            raise RuntimeError(
                "Не найдено данных ни для сценария рекомендаций, ни для кластеров"
            )

    if profile in rec_profiles:
        state.cache.ensure_standard_data()
        selected = rec_profiles[profile]
        base = rec_ops
    elif profile in cluster_profiles:
        state.cache.ensure_cluster_data()
        selected = cluster_profiles[profile]
        base = cluster_ops
    else:
        allowed = [*rec_profiles.keys(), *cluster_profiles.keys(), "auto"]
        raise ValueError(
            f"Неизвестный профиль '{profile}'. Доступные значения: {', '.join(allowed)}"
        )

    operations: list[OperationSpec] = []
    for key, weight in selected.items():
        spec = base[key]
        operations.append(
            OperationSpec(
                name=spec.name,
                op_type=spec.op_type,
                weight=weight,
                func=spec.func,
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
    session_factory = ensure_db_modules()["session_factory"]
    if session_factory is None:
        raise RuntimeError("Сессия базы данных не инициализирована")
    with session_factory() as session:
        return func(session, state, rng, *extra)


def op_fetch_student(session, state: SharedState, rng: random.Random):
    students_module = ensure_db_modules()["students_crud"]
    participant = state.cache.random_participant(rng)
    students_module.get_student_by_participant_id(session, participant)


def op_fetch_recommendations(session, state: SharedState, rng: random.Random):
    recommendations_module = ensure_db_modules()["recommendations_crud"]
    student_id = state.cache.random_student_id(rng)
    recommendations_module.get_recommendations_for_student(session, student_id, limit=20)


def op_fetch_events(session, state: SharedState, rng: random.Random):
    events_model = ensure_db_modules()["events_model"]
    limit = rng.randint(10, 50)
    session.execute(select(events_model.id, events_model.title).limit(limit)).all()


def op_list_feedback(session, state: SharedState, rng: random.Random):
    feedback_module = ensure_db_modules()["feedback_crud"]
    try:
        student_id = state.cache.random_student_id(rng)
    except SkipOperation as exc:
        raise SkipOperation("Нет студентов для чтения отзывов") from exc
    feedback_module.get_feedbacks_by_student(session, student_id)


def op_create_feedback(session, state: SharedState, rng: random.Random):
    feedback_module = ensure_db_modules()["feedback_crud"]
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
    feedback_module = ensure_db_modules()["feedback_crud"]
    feedback_id = state.cache.random_feedback_id(rng)
    new_rating = rng.randint(1, 5)
    new_comment = rng.choice(COMMENT_TEMPLATES)
    feedback_module.update_feedback(
        session,
        feedback_id=feedback_id,
        rating=new_rating,
        comment=new_comment,
    )


def op_list_clusters(session, state: SharedState, rng: random.Random):  # noqa: ARG001
    clusters_module = ensure_db_modules()["clusters_crud"]
    clusters_module.get_all_clusters(session)


def op_list_directions(session, state: SharedState, rng: random.Random):  # noqa: ARG001
    directions_module = ensure_db_modules()["directions_crud"]
    limit = rng.randint(10, 100)
    directions_module.get_all_directions(session, limit=limit)


def op_cluster_overview(session, state: SharedState, rng: random.Random):
    modules = ensure_db_modules()
    clusters_model = modules["clusters_model"]
    directions_model = modules["directions_model"]
    cluster_id = state.cache.random_cluster_id(rng)
    session.execute(select(clusters_model).where(clusters_model.id == cluster_id)).scalar_one_or_none()
    session.execute(
        select(directions_model.id, directions_model.title)
        .where(directions_model.cluster_id == cluster_id)
        .limit(200)
    ).all()


def op_create_direction(session, state: SharedState, rng: random.Random):
    directions_module = ensure_db_modules()["directions_crud"]
    cluster_id = state.cache.random_cluster_id(rng)
    title = f"LoadTest Direction {uuid4().hex[:8]}"
    direction = directions_module.create_direction(session, title=title, cluster_id=cluster_id)
    state.register_direction(direction.id, cluster_id, is_new=True)


def op_update_direction(session, state: SharedState, rng: random.Random):
    modules = ensure_db_modules()
    directions_model = modules["directions_model"]
    direction_id = state.pick_temp_direction(rng)
    new_title = f"Updated {uuid4().hex[:6]}"
    session.execute(
        update(directions_model).where(directions_model.id == direction_id).values(title=new_title)
    )
    session.commit()


def op_delete_direction(session, state: SharedState, rng: random.Random):
    directions_module = ensure_db_modules()["directions_crud"]
    direction_id = state.pick_temp_direction(rng)
    deleted = directions_module.delete_direction(session, direction_id)
    if not deleted:
        raise SkipOperation("Направление уже удалено")
    state.mark_direction_deleted(direction_id)


def op_reassign_direction(session, state: SharedState, rng: random.Random):
    modules = ensure_db_modules()
    directions_model = modules["directions_model"]
    direction_id = state.pick_temp_direction(rng)
    new_cluster = state.cache.random_cluster_id(rng)
    session.execute(
        update(directions_model).where(directions_model.id == direction_id).values(cluster_id=new_cluster)
    )
    session.commit()
    state.update_direction_cluster(direction_id, new_cluster)


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

    modules = ensure_db_modules()
    session_factory = modules["session_factory"]
    feedback_module = modules["feedback_crud"]
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


def cleanup_directions(state: SharedState, logger: logging.Logger) -> None:
    if not state.cleanup:
        logger.info(
            "Флаг очистки выключен, сохранено %d временных направлений",
            len(state.created_direction_ids),
        )
        return
    if not state.created_direction_ids:
        logger.info("Во время теста не создано новых направлений")
        return

    modules = ensure_db_modules()
    session_factory = modules["session_factory"]
    directions_module = modules["directions_crud"]
    if session_factory is None or directions_module is None:
        logger.error("Не удалось инициализировать зависимости для очистки направлений")
        return

    initial_count = len(state.created_direction_ids)
    with session_factory() as session:
        for direction_id in list(state.created_direction_ids):
            try:
                directions_module.delete_direction(session, direction_id)
                state.mark_direction_deleted(direction_id)
            except Exception:  # noqa: BLE001
                logger.exception("Не удалось удалить временное направление %s", direction_id)
    removed = initial_count - len(state.created_direction_ids)
    logger.info("Удалено временных направлений: %d", removed)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Нагрузочное тестирование базы данных Supabase")
    parser.add_argument("--duration", type=float, default=600.0, help="Желаемая длительность теста, секунды")
    parser.add_argument("--min-duration", type=float, default=120.0, help="Минимально допустимая длительность теста")
    parser.add_argument("--allow-short-runs", action="store_true", help="Разрешить запуск короче минимального времени")
    parser.add_argument("--concurrency", type=int, default=16, help="Количество параллельных воркеров")
    parser.add_argument(
        "--profile",
        choices=[
            "auto",
            "read-heavy",
            "write-heavy",
            "mixed",
            "clusters-read",
            "clusters-write",
            "clusters-mixed",
        ],
        default="auto",
        help="Профиль нагрузки",
    )
    parser.add_argument("--prefetch-limit", type=int, default=2000, help="Сколько записей предзагружать из справочников")
    parser.add_argument("--max-retries", type=int, default=3, help="Сколько повторов выполнять при транзиентных ошибках")
    parser.add_argument("--backoff", type=float, default=0.5, help="Базовая задержка (сек) перед повтором транзиентной ошибки")
    parser.add_argument("--log-dir", default="logs/db", help="Каталог для логов и отчётов")
    parser.add_argument("--raw-metrics-file", help="Путь к CSV с покадровыми задержками")
    parser.add_argument("--summary-file", help="Путь к JSON с агрегированными метриками")
    parser.add_argument("--per-type-file", help="JSON со сводкой по типам операций")
    parser.add_argument("--timeline-file", help="NDJSON с временной шкалой операций")
    parser.add_argument("--errors-file", help="NDJSON с ошибками и повторами")
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Не удалять созданные во время теста отзывы и направления",
    )
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
    except KeyboardInterrupt:
        logger.warning("Тест прерван пользователем")
        return
    except Exception as exc:
        logger.exception("Тест завершился ошибкой: %s", exc)
        raise
    else:
        logger.info("Нагрузочный тест завершён")
    finally:
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
    cleanup_directions(state, logger)


if __name__ == "__main__":
    main()

