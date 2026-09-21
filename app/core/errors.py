"""Standardized application exceptions and error codes for SIH 2026 PS26011."""
from typing import Any, Dict, Optional
from fastapi import status


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    INVALID_GEOMETRY = "INVALID_GEOMETRY"
    INVALID_CRS = "INVALID_CRS"
    INVALID_ML_SCHEMA = "INVALID_ML_SCHEMA"
    UNSUPPORTED_SCHEMA_VERSION = "UNSUPPORTED_SCHEMA_VERSION"
    JOB_FAILED = "JOB_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"


class AppError(Exception):
    """Base exception for all structured application errors."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.VALIDATION_ERROR,
            message=message,
            status_code=422,
            details=details,
        )


class InvalidGeometryError(AppError):
    def __init__(self, message: str = "Invalid geometry supplied", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.INVALID_GEOMETRY,
            message=message,
            status_code=422,
            details=details,
        )


class InvalidCRSError(AppError):
    def __init__(self, message: str = "Invalid or unsupported Coordinate Reference System", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.INVALID_CRS,
            message=message,
            status_code=422,
            details=details,
        )


class UnsupportedSchemaVersionError(AppError):
    def __init__(self, message: str = "Unsupported ML contract schema version", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.UNSUPPORTED_SCHEMA_VERSION,
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class ConflictError(AppError):
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.CONFLICT,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class DuplicateResourceError(AppError):
    def __init__(self, message: str = "Resource already exists", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.DUPLICATE_RESOURCE,
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class AuthenticationError(AppError):
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.AUTHENTICATION_ERROR,
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(AppError):
    def __init__(self, message: str = "Access forbidden", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code=ErrorCode.AUTHORIZATION_ERROR,
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


# Alias for AuthorizationError (403 Forbidden)
ForbiddenError = AuthorizationError
