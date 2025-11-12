"""
Централизованный обработчик ошибок для FastAPI.
"""
import logging
import traceback
from typing import Union
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError
import sentry_sdk

from src.core.exceptions import BaseAppException

logger = logging.getLogger(__name__)


async def base_exception_handler(request: Request, exc: BaseAppException) -> JSONResponse:
    """Обработчик для базовых исключений приложения."""
    logger.error(
        f"Application error: {exc.message}",
        extra={
            "error_type": type(exc).__name__,
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.message,
            "details": exc.details,
            "type": type(exc).__name__,
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обработчик ошибок валидации Pydantic."""
    errors = exc.errors()
    logger.warning(
        f"Validation error: {errors}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "errors": errors,
        }
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": True,
            "message": "Ошибка валидации данных",
            "details": errors,
            "type": "ValidationError",
        }
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Обработчик HTTP исключений."""
    logger.warning(
        f"HTTP error: {exc.status_code} - {exc.detail}",
        extra={
            "status_code": exc.status_code,
            "path": request.url.path,
            "method": request.method,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "message": exc.detail,
            "type": "HTTPException",
        }
    )


async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Обработчик ошибок SQLAlchemy."""
    logger.error(
        f"Database error: {str(exc)}",
        extra={
            "error_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Ошибка работы с базой данных",
            "type": "DatabaseError",
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик для всех необработанных исключений."""
    # Отправляем в Sentry
    sentry_sdk.capture_exception(
        exc,
        contexts={
            "request": {
                "url": str(request.url),
                "method": request.method,
                "path": request.url.path,
            }
        }
    )
    
    logger.critical(
        f"Unhandled exception: {type(exc).__name__}: {str(exc)}",
        extra={
            "error_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
            "traceback": traceback.format_exc(),
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": True,
            "message": "Внутренняя ошибка сервера",
            "type": "InternalServerError",
        }
    )

