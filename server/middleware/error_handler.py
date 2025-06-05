"""
Error Handling Middleware - Task 5.2
Comprehensive error handling with proper HTTP status codes
"""

import logging
import traceback
from typing import Union, Dict, Any
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import ValidationError as PydanticValidationError
import time

logger = logging.getLogger(__name__)

class APIError(Exception):
    """Base API error class"""
    def __init__(self, message: str, status_code: int = 500, error_code: str = None):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or f"API_ERROR_{status_code}"
        super().__init__(self.message)

class AuthenticationError(APIError):
    """Authentication related errors"""
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message, 401, "AUTHENTICATION_ERROR")

class AuthorizationError(APIError):
    """Authorization related errors"""
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, 403, "AUTHORIZATION_ERROR")

class ValidationError(APIError):
    """Validation related errors"""
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message, 400, "VALIDATION_ERROR")

class DatabaseError(APIError):
    """Database related errors"""
    def __init__(self, message: str = "Database operation failed"):
        super().__init__(message, 500, "DATABASE_ERROR")

class RateLimitError(APIError):
    """Rate limiting errors"""
    def __init__(self, message: str = "Rate limit exceeded", retry_after: int = 60):
        super().__init__(message, 429, "RATE_LIMIT_ERROR")
        self.retry_after = retry_after

def create_error_response(
    status_code: int,
    message: str,
    error_code: str = None,
    details: Union[str, Dict, list] = None,
    request_id: str = None
) -> JSONResponse:
    """
    Create standardized error response
    """
    error_data = {
        "error": True,
        "message": message,
        "status_code": status_code,
        "timestamp": time.time()
    }
    
    if error_code:
        error_data["error_code"] = error_code
    
    if details:
        error_data["details"] = details
    
    if request_id:
        error_data["request_id"] = request_id
    
    return JSONResponse(
        status_code=status_code,
        content=error_data
    )

async def api_error_handler(request: Request, exc: APIError):
    """Handle custom API errors"""
    request_id = getattr(request.state, 'request_id', None)
    
    logger.error(
        f"API Error: {exc.error_code} - {exc.message} "
        f"(Request: {request.method} {request.url.path})"
    )
    
    response = create_error_response(
        status_code=exc.status_code,
        message=exc.message,
        error_code=exc.error_code,
        request_id=request_id
    )
    
    # Add retry-after header for rate limit errors
    if isinstance(exc, RateLimitError) and hasattr(exc, 'retry_after'):
        response.headers["Retry-After"] = str(exc.retry_after)
    
    return response

async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle FastAPI HTTP exceptions"""
    request_id = getattr(request.state, 'request_id', None)
    
    logger.warning(
        f"HTTP Exception: {exc.status_code} - {exc.detail} "
        f"(Request: {request.method} {request.url.path})"
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code=f"HTTP_ERROR_{exc.status_code}",
        request_id=request_id
    )

async def starlette_http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle Starlette HTTP exceptions"""
    request_id = getattr(request.state, 'request_id', None)
    
    logger.warning(
        f"Starlette HTTP Exception: {exc.status_code} - {exc.detail} "
        f"(Request: {request.method} {request.url.path})"
    )
    
    return create_error_response(
        status_code=exc.status_code,
        message=exc.detail,
        error_code=f"HTTP_ERROR_{exc.status_code}",
        request_id=request_id
    )

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors"""
    request_id = getattr(request.state, 'request_id', None)
    
    # Extract validation error details
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(x) for x in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    logger.warning(
        f"Validation Error: {len(errors)} validation errors "
        f"(Request: {request.method} {request.url.path})"
    )
    
    return create_error_response(
        status_code=422,
        message="Request validation failed",
        error_code="VALIDATION_ERROR",
        details=errors,
        request_id=request_id
    )

async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle SQLAlchemy database errors"""
    request_id = getattr(request.state, 'request_id', None)
    
    # Log full traceback for debugging
    logger.error(
        f"Database Error: {type(exc).__name__} - {str(exc)} "
        f"(Request: {request.method} {request.url.path})\n"
        f"Traceback: {traceback.format_exc()}"
    )
    
    # Different handling for different types of DB errors
    if isinstance(exc, IntegrityError):
        message = "Data integrity violation"
        if "UNIQUE constraint failed" in str(exc):
            message = "Duplicate entry - record already exists"
        elif "FOREIGN KEY constraint failed" in str(exc):
            message = "Invalid reference - related record not found"
    else:
        message = "Database operation failed"
    
    return create_error_response(
        status_code=500,
        message=message,
        error_code="DATABASE_ERROR",
        request_id=request_id
    )

async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    request_id = getattr(request.state, 'request_id', None)
    
    # Log full traceback for debugging
    logger.error(
        f"Unexpected Error: {type(exc).__name__} - {str(exc)} "
        f"(Request: {request.method} {request.url.path})\n"
        f"Traceback: {traceback.format_exc()}"
    )
    
    return create_error_response(
        status_code=500,
        message="Internal server error",
        error_code="INTERNAL_SERVER_ERROR",
        details=str(exc) if logger.isEnabledFor(logging.DEBUG) else None,
        request_id=request_id
    )

class ErrorHandlerMiddleware:
    """
    Error handling middleware
    Catches and handles various types of exceptions
    """
    
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        try:
            await self.app(scope, receive, send)
        except Exception as exc:
            # This middleware will catch any unhandled exceptions
            # that weren't caught by the FastAPI exception handlers
            request = Request(scope, receive)
            
            if isinstance(exc, (HTTPException, StarletteHTTPException)):
                response = await http_exception_handler(request, exc)
            elif isinstance(exc, RequestValidationError):
                response = await validation_exception_handler(request, exc)
            elif isinstance(exc, SQLAlchemyError):
                response = await sqlalchemy_exception_handler(request, exc)
            elif isinstance(exc, APIError):
                response = await api_error_handler(request, exc)
            else:
                response = await general_exception_handler(request, exc)
            
            await response(scope, receive, send)

def setup_error_handlers(app):
    """
    Setup error handlers for FastAPI application
    """
    # Custom API errors
    app.add_exception_handler(APIError, api_error_handler)
    
    # FastAPI/Starlette exceptions
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(StarletteHTTPException, starlette_http_exception_handler)
    
    # Validation errors
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(PydanticValidationError, validation_exception_handler)
    
    # Database errors
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)
    
    # General exception handler (catch-all)
    app.add_exception_handler(Exception, general_exception_handler)
    
    logger.info("Error handlers registered successfully")

# Utility functions for raising specific errors
def raise_authentication_error(message: str = "Authentication failed"):
    """Raise authentication error"""
    raise AuthenticationError(message)

def raise_authorization_error(message: str = "Access denied"):
    """Raise authorization error"""
    raise AuthorizationError(message)

def raise_validation_error(message: str = "Validation failed"):
    """Raise validation error"""
    raise ValidationError(message)

def raise_database_error(message: str = "Database operation failed"):
    """Raise database error"""
    raise DatabaseError(message) 