from __future__ import annotations

import contextlib
import io
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.api.dependencies import db_dependency
from src.core.database.reset_database import reset_database
from src.recommendation.events.score_calculation import recalculate_scores_for_all_students
from src.recommendation.events.utils import (
    insert_events_to_db,
    load_events_from_json_file,
    process_events_from_csv,
)

from scripts.database_mv.manage import (
    CLUSTER_TOP_K,
    SIMILARITY_THRESHOLD,
    EVENTS_INPUT_FILE,
    EVENTS_OUTPUT_FILE,
    _ensure_event_paths,
)
from scripts.database_mv.helpers.directions_clusters import run_directions_pipeline
from scripts.database_mv.helpers.preprocess_excel import (
    INPUT_FILE as DIRECTIONS_INPUT_FILE,
    OUTPUT_FILE as DIRECTIONS_OUTPUT_FILE,
    preprocess_excel,
)


router = APIRouter()


class MaintenanceInfoResponse(BaseModel):
    events_input_file: str
    events_output_file: str
    directions_input_file: str
    directions_output_file: str
    cluster_top_k_default: int
    similarity_threshold_default: float


class EventsProcessRequest(BaseModel):
    input_file: str | None = None
    output_file: str | None = None


class EventsProcessResponse(BaseModel):
    processed: int
    input_file: str
    output_file: str
    log: str | None = None


class EventsLoadRequest(BaseModel):
    input_file: str | None = None
    assign_clusters: bool = False
    cluster_top_k: int | None = Field(None, ge=1)
    similarity_threshold: float | None = Field(None, ge=0.0, le=1.0)


class EventsLoadResponse(BaseModel):
    added: int
    skipped: int
    total_in_file: int
    assign_clusters: bool
    cluster_top_k: int
    similarity_threshold: float
    output_file: str
    log: str | None = None


class RecommendationsRecalculateRequest(BaseModel):
    min_score: float = Field(0.0, ge=0.0, le=1.0)
    batch_size: int = Field(1000, ge=1)


class RecommendationsRecalculateResponse(BaseModel):
    stats: dict[str, int]
    log: str | None = None


class DirectionsPreprocessRequest(BaseModel):
    input_file: str | None = None
    output_file: str | None = None


class DirectionsPreprocessResponse(BaseModel):
    rows: int
    columns: int
    input_file: str
    output_file: str
    log: str | None = None


class DirectionsClusterRequest(BaseModel):
    force_preprocess: bool = False


class DirectionsClusterResponse(BaseModel):
    message: str
    log: str | None = None


class ResetDatabaseRequest(BaseModel):
    confirm: bool = False


class ResetDatabaseResponse(BaseModel):
    message: str
    log: str | None = None


class OperationExecutionError(Exception):
    """Wraps errors raised during operation execution together with captured logs."""

    def __init__(self, original: Exception, log: str):
        super().__init__(str(original))
        self.original = original
        self.log = log


def _execute_with_logs(func, *args, **kwargs) -> tuple[object, str]:
    buffer = io.StringIO()
    try:
        with contextlib.redirect_stdout(buffer):
            result = func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 - bubble up with captured log
        raise OperationExecutionError(exc, buffer.getvalue()) from exc
    return result, buffer.getvalue()


def _http_error_from_exception(exc: OperationExecutionError, not_found_types: tuple[type[Exception], ...] = (FileNotFoundError,)) -> HTTPException:
    status_code = (
        status.HTTP_404_NOT_FOUND
        if isinstance(exc.original, not_found_types)
        else status.HTTP_500_INTERNAL_SERVER_ERROR
    )
    detail = {"message": str(exc.original)}
    if exc.log:
        detail["log"] = exc.log
    return HTTPException(status_code=status_code, detail=detail)


@router.get("/info", response_model=MaintenanceInfoResponse)
def get_maintenance_info() -> MaintenanceInfoResponse:
    return MaintenanceInfoResponse(
        events_input_file=str(Path(EVENTS_INPUT_FILE)),
        events_output_file=str(Path(EVENTS_OUTPUT_FILE)),
        directions_input_file=str(Path(DIRECTIONS_INPUT_FILE)),
        directions_output_file=str(Path(DIRECTIONS_OUTPUT_FILE)),
        cluster_top_k_default=CLUSTER_TOP_K,
        similarity_threshold_default=SIMILARITY_THRESHOLD,
    )


@router.post("/events/process-csv", response_model=EventsProcessResponse)
async def process_events_csv(request: Request) -> EventsProcessResponse:
    """Обрабатывает CSV файл мероприятий. Можно загрузить файл или указать путь."""
    _ensure_event_paths()
    
    content_type = request.headers.get("content-type", "").lower()
    file = None
    input_file = None
    output_file = None
    
    # Парсим запрос в зависимости от content-type
    if "multipart/form-data" in content_type:
        form = await request.form()
        if "file" in form:
            file = form["file"]
        input_file = form.get("input_file")
        output_file = form.get("output_file")
    else:
        # По умолчанию пытаемся парсить как JSON
        try:
            body = await request.json()
            input_file = body.get("input_file")
            output_file = body.get("output_file")
        except Exception:
            # Если не JSON, используем значения по умолчанию
            pass
    
    # Определяем входной файл
    if file:
        # Сохраняем загруженный файл во временную директорию
        temp_dir = Path(tempfile.gettempdir()) / "vkr_events"
        temp_dir.mkdir(parents=True, exist_ok=True)
        filename = getattr(file, "filename", "uploaded.csv") or "uploaded.csv"
        input_path = temp_dir / filename
        file_content = await file.read()
        with input_path.open("wb") as f:
            f.write(file_content)
    elif input_file:
        input_path = Path(input_file)
    else:
        input_path = Path(EVENTS_INPUT_FILE)
    
    # Определяем выходной файл
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = Path(EVENTS_OUTPUT_FILE)
    
    # Создаём директорию для выходного файла
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл не найден: {input_path}",
        )
    
    try:
        events, log = _execute_with_logs(process_events_from_csv, input_path, output_path)
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    return EventsProcessResponse(
        processed=len(events),
        input_file=str(input_path),
        output_file=str(output_path),
        log=log or None,
    )


@router.post("/events/load-json", response_model=EventsLoadResponse)
async def load_events_from_json(request: Request) -> EventsLoadResponse:
    """Загружает мероприятия из JSON в БД. Можно загрузить файл или указать путь."""
    _ensure_event_paths()
    
    content_type = request.headers.get("content-type", "").lower()
    file = None
    input_file = None
    assign_clusters = False
    cluster_top_k = None
    similarity_threshold = None
    
    # Парсим запрос в зависимости от content-type
    if "multipart/form-data" in content_type:
        form = await request.form()
        if "file" in form:
            file = form["file"]
        input_file = form.get("input_file")
        assign_clusters = form.get("assign_clusters", "false").lower() == "true"
        if form.get("cluster_top_k"):
            cluster_top_k = int(form["cluster_top_k"])
        if form.get("similarity_threshold"):
            similarity_threshold = float(form["similarity_threshold"])
    else:
        # По умолчанию пытаемся парсить как JSON
        try:
            body = await request.json()
            input_file = body.get("input_file")
            assign_clusters = body.get("assign_clusters", False)
            cluster_top_k = body.get("cluster_top_k")
            similarity_threshold = body.get("similarity_threshold")
        except Exception:
            # Если не JSON, используем значения по умолчанию
            pass
    
    # Определяем входной файл
    json_path = None
    if file:
        # Сохраняем загруженный файл во временную директорию
        temp_dir = Path(tempfile.gettempdir()) / "vkr_events"
        temp_dir.mkdir(parents=True, exist_ok=True)
        filename = getattr(file, "filename", "uploaded.json") or "uploaded.json"
        json_path = temp_dir / filename
        file_content = await file.read()
        with json_path.open("wb") as f:
            f.write(file_content)
    elif input_file:
        json_path = Path(input_file)
    else:
        json_path = Path(EVENTS_OUTPUT_FILE)
    
    if not json_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"JSON-файл не найден: {json_path}",
        )

    try:
        events, load_log = _execute_with_logs(load_events_from_json_file, json_path)
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    if not events:
        detail = {"message": "JSON-файл не содержит мероприятий"}
        if load_log:
            detail["log"] = load_log
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    
    # Получаем параметры из запроса
    assign_clusters_val = assign_clusters
    cluster_top_k_val = cluster_top_k or CLUSTER_TOP_K
    similarity_threshold_val = similarity_threshold or SIMILARITY_THRESHOLD

    try:
        (added, skipped), insert_log = _execute_with_logs(
            insert_events_to_db,
            events,
            assign_clusters=assign_clusters_val,
            cluster_top_k=cluster_top_k_val,
            similarity_threshold=similarity_threshold_val,
        )
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    combined_log = "\n".join(part for part in (load_log, insert_log) if part)

    return EventsLoadResponse(
        added=added,
        skipped=skipped,
        total_in_file=len(events),
        assign_clusters=assign_clusters_val,
        cluster_top_k=cluster_top_k_val,
        similarity_threshold=similarity_threshold_val,
        output_file=str(json_path),
        log=combined_log or None,
    )


@router.post("/recommendations/recalculate", response_model=RecommendationsRecalculateResponse)
def recalculate_recommendations(
    payload: RecommendationsRecalculateRequest,
    db: Session = Depends(db_dependency),
) -> RecommendationsRecalculateResponse:
    try:
        stats, log = _execute_with_logs(
            recalculate_scores_for_all_students,
            db,
            min_score=payload.min_score,
            batch_size=payload.batch_size,
        )
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    return RecommendationsRecalculateResponse(stats=stats, log=log or None)


@router.post("/directions/preprocess", response_model=DirectionsPreprocessResponse)
async def preprocess_directions(request: Request) -> DirectionsPreprocessResponse:
    """Предобрабатывает Excel файл направлений. Можно загрузить файл или указать путь."""
    content_type = request.headers.get("content-type", "").lower()
    file = None
    input_file = None
    output_file = None
    
    # Парсим запрос в зависимости от content-type
    if "multipart/form-data" in content_type:
        form = await request.form()
        if "file" in form:
            file = form["file"]
        input_file = form.get("input_file")
        output_file = form.get("output_file")
    else:
        # По умолчанию пытаемся парсить как JSON
        try:
            body = await request.json()
            input_file = body.get("input_file")
            output_file = body.get("output_file")
        except Exception:
            # Если не JSON, используем значения по умолчанию
            pass
    
    # Определяем входной файл
    if file:
        # Сохраняем загруженный файл во временную директорию
        temp_dir = Path(tempfile.gettempdir()) / "vkr_directions"
        temp_dir.mkdir(parents=True, exist_ok=True)
        filename = getattr(file, "filename", "uploaded.xlsx") or "uploaded.xlsx"
        input_path = temp_dir / filename
        file_content = await file.read()
        with input_path.open("wb") as f:
            f.write(file_content)
    elif input_file:
        input_path = Path(input_file)
    else:
        input_path = Path(DIRECTIONS_INPUT_FILE)
    
    # Определяем выходной файл
    if output_file:
        output_path = Path(output_file)
    else:
        output_path = Path(DIRECTIONS_OUTPUT_FILE)
    
    # Создаём директорию для выходного файла
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not input_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Файл не найден: {input_path}",
        )
    
    # Временно переопределяем пути в функции preprocess_excel
    from scripts.database_mv.helpers.preprocess_excel import preprocess_excel as original_preprocess
    
    def preprocess_with_paths():
        from scripts.database_mv.helpers.preprocess_excel import INPUT_FILE, OUTPUT_FILE
        # Временно заменяем пути
        import scripts.database_mv.helpers.preprocess_excel as preprocess_module
        original_input = preprocess_module.INPUT_FILE
        original_output = preprocess_module.OUTPUT_FILE
        try:
            preprocess_module.INPUT_FILE = input_path
            preprocess_module.OUTPUT_FILE = output_path
            return original_preprocess()
        finally:
            preprocess_module.INPUT_FILE = original_input
            preprocess_module.OUTPUT_FILE = original_output
    
    try:
        df, log = _execute_with_logs(preprocess_with_paths)
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    rows = int(getattr(df, "shape", (0, 0))[0]) if df is not None else 0
    columns = int(getattr(df, "shape", (0, 0))[1]) if df is not None else 0

    return DirectionsPreprocessResponse(
        rows=rows,
        columns=columns,
        input_file=str(input_path),
        output_file=str(output_path),
        log=log or None,
    )


@router.post("/directions/clusterize", response_model=DirectionsClusterResponse)
def clusterize_directions(request: DirectionsClusterRequest) -> DirectionsClusterResponse:
    try:
        _, log = _execute_with_logs(run_directions_pipeline, force_preprocess=request.force_preprocess)
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    message = (
        "Кластеризация направлений выполнена (с предварительной обработкой)."
        if request.force_preprocess
        else "Кластеризация направлений выполнена."
    )

    return DirectionsClusterResponse(message=message, log=log or None)


@router.post("/database/reset", response_model=ResetDatabaseResponse)
def reset_database_endpoint(request: ResetDatabaseRequest) -> ResetDatabaseResponse:
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Необходимо подтвердить операцию сброса базы данных.",
        )

    try:
        _, log = _execute_with_logs(reset_database)
    except OperationExecutionError as exc:
        raise _http_error_from_exception(exc)

    return ResetDatabaseResponse(message="База данных сброшена.", log=log or None)


