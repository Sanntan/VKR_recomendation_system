"""
Тесты для исключений.
"""
import pytest
from src.core.exceptions import (
    BaseAppException,
    DatabaseError,
    ValidationError,
    NotFoundError,
    AuthenticationError,
    AuthorizationError,
    ExternalServiceError
)


class TestExceptions:
    """Тесты для исключений."""
    
    def test_base_exception(self):
        """Тест базового исключения."""
        exc = BaseAppException("Test error", status_code=400)
        assert exc.message == "Test error"
        assert exc.status_code == 400
        assert exc.details == {}
    
    def test_base_exception_with_details(self):
        """Тест базового исключения с деталями."""
        details = {"field": "value"}
        exc = BaseAppException("Test error", status_code=400, details=details)
        assert exc.details == details
    
    def test_database_error(self):
        """Тест ошибки базы данных."""
        exc = DatabaseError("DB error")
        assert exc.message == "DB error"
        assert exc.status_code == 500
    
    def test_validation_error(self):
        """Тест ошибки валидации."""
        exc = ValidationError("Invalid data")
        assert exc.message == "Invalid data"
        assert exc.status_code == 400
    
    def test_not_found_error(self):
        """Тест ошибки не найдено."""
        exc = NotFoundError("Not found")
        assert exc.message == "Not found"
        assert exc.status_code == 404
    
    def test_authentication_error(self):
        """Тест ошибки аутентификации."""
        exc = AuthenticationError("Auth failed")
        assert exc.message == "Auth failed"
        assert exc.status_code == 401
    
    def test_authorization_error(self):
        """Тест ошибки авторизации."""
        exc = AuthorizationError("Forbidden")
        assert exc.message == "Forbidden"
        assert exc.status_code == 403
    
    def test_external_service_error(self):
        """Тест ошибки внешнего сервиса."""
        exc = ExternalServiceError("Service unavailable")
        assert exc.message == "Service unavailable"
        assert exc.status_code == 502

