"""
Request Logging and Audit Trail Middleware - Task 5.4
Implements comprehensive request logging and security event auditing
"""

import os
import json
import time
import uuid
import logging
from datetime import datetime
from typing import Dict, Optional, Any, List
from fastapi import Request, Response
from fastapi.routing import APIRoute
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
import hashlib

# Configure audit logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# Create audit log handler if not exists
if not audit_logger.handlers:
    audit_handler = logging.FileHandler("audit.log")
    audit_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    audit_handler.setFormatter(audit_formatter)
    audit_logger.addHandler(audit_handler)

class SecurityEvent:
    """Security event types for audit logging"""
    
    # Authentication events
    LOGIN_SUCCESS = "LOGIN_SUCCESS"
    LOGIN_FAILURE = "LOGIN_FAILURE"
    LOGOUT = "LOGOUT"
    TOKEN_REFRESH = "TOKEN_REFRESH"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    PASSWORD_RESET_REQUEST = "PASSWORD_RESET_REQUEST"
    PASSWORD_RESET_SUCCESS = "PASSWORD_RESET_SUCCESS"
    
    # Authorization events
    ACCESS_DENIED = "ACCESS_DENIED"
    PRIVILEGE_ESCALATION_ATTEMPT = "PRIVILEGE_ESCALATION_ATTEMPT"
    
    # Data events
    CHARACTER_CREATED = "CHARACTER_CREATED"
    CHARACTER_UPDATED = "CHARACTER_UPDATED"
    CHARACTER_DELETED = "CHARACTER_DELETED"
    CHARACTER_SHARED = "CHARACTER_SHARED"
    CHARACTER_EXPORTED = "CHARACTER_EXPORTED"
    CHARACTER_IMPORTED = "CHARACTER_IMPORTED"
    
    # Security events
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SUSPICIOUS_ACTIVITY = "SUSPICIOUS_ACTIVITY"
    SQL_INJECTION_ATTEMPT = "SQL_INJECTION_ATTEMPT"
    XSS_ATTEMPT = "XSS_ATTEMPT"
    
    # System events
    DATABASE_BACKUP = "DATABASE_BACKUP"
    DATABASE_RESTORE = "DATABASE_RESTORE"
    ADMIN_ACTION = "ADMIN_ACTION"

class AuditLogger:
    """Centralized audit logging system"""
    
    def __init__(self):
        self.logger = audit_logger
        self.sensitive_fields = {
            "password", "hashed_password", "token", "refresh_token",
            "access_token", "secret", "key", "authorization"
        }
    
    def log_security_event(
        self,
        event_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        severity: str = "INFO",
        request_id: Optional[str] = None
    ):
        """Log security event with standardized format"""
        
        event_data = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "severity": severity,
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "request_id": request_id,
            "details": self._sanitize_details(details)
        }
        
        # Remove None values
        event_data = {k: v for k, v in event_data.items() if v is not None}
        
        # Log the event
        log_message = f"SECURITY_EVENT: {json.dumps(event_data)}"
        
        if severity == "CRITICAL":
            self.logger.critical(log_message)
        elif severity == "ERROR":
            self.logger.error(log_message)
        elif severity == "WARNING":
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def log_request(
        self,
        method: str,
        path: str,
        status_code: int,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        duration_ms: Optional[float] = None,
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
        request_id: Optional[str] = None,
        query_params: Optional[Dict] = None,
        errors: Optional[List[str]] = None
    ):
        """Log HTTP request with details"""
        
        request_data = {
            "type": "HTTP_REQUEST",
            "timestamp": datetime.utcnow().isoformat(),
            "method": method,
            "path": path,
            "status_code": status_code,
            "user_id": user_id,
            "username": username,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "duration_ms": duration_ms,
            "request_size": request_size,
            "response_size": response_size,
            "request_id": request_id,
            "query_params": self._sanitize_details(query_params),
            "errors": errors
        }
        
        # Remove None values
        request_data = {k: v for k, v in request_data.items() if v is not None}
        
        log_message = f"HTTP_REQUEST: {json.dumps(request_data)}"
        
        # Log based on status code
        if status_code >= 500:
            self.logger.error(log_message)
        elif status_code >= 400:
            self.logger.warning(log_message)
        else:
            self.logger.info(log_message)
    
    def _sanitize_details(self, details: Optional[Dict]) -> Optional[Dict]:
        """Remove sensitive information from details"""
        if not details:
            return details
        
        sanitized = {}
        for key, value in details.items():
            if any(sensitive in key.lower() for sensitive in self.sensitive_fields):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, dict):
                sanitized[key] = self._sanitize_details(value)
            else:
                sanitized[key] = value
        
        return sanitized

class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """Middleware for logging all HTTP requests and responses"""
    
    def __init__(self, app, audit_logger: AuditLogger = None):
        super().__init__(app)
        self.audit_logger = audit_logger or AuditLogger()
        self.exclude_paths = {
            "/docs", "/redoc", "/openapi.json",
            "/health", "/metrics"
        }
        self.log_request_body = os.getenv("LOG_REQUEST_BODY", "false").lower() == "true"
        self.log_response_body = os.getenv("LOG_RESPONSE_BODY", "false").lower() == "true"
    
    async def dispatch(self, request: Request, call_next):
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Skip logging for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Start timing
        start_time = time.time()
        
        # Extract request information
        method = request.method
        path = request.url.path
        ip_address = self._get_client_ip(request)
        user_agent = request.headers.get("user-agent", "")
        query_params = dict(request.query_params) if request.query_params else None
        
        # Get request size
        request_size = int(request.headers.get("content-length", 0))
        
        # Extract user information if available
        user_id = None
        username = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = request.state.user.id
            username = request.state.user.username
        
        # Log request body if enabled (for debugging)
        request_body = None
        if self.log_request_body and request_size > 0:
            try:
                body = await request.body()
                request_body = body.decode('utf-8')[:1000]  # Limit size
            except Exception:
                request_body = "[BINARY_DATA]"
        
        # Process request
        try:
            response = await call_next(request)
            status_code = response.status_code
            errors = None
        except Exception as e:
            status_code = 500
            errors = [str(e)]
            # Re-raise the exception
            raise
        finally:
            # Calculate duration
            duration_ms = round((time.time() - start_time) * 1000, 2)
            
            # Get response size
            response_size = None
            if 'response' in locals():
                response_size = int(response.headers.get("content-length", 0))
            
            # Log the request
            self.audit_logger.log_request(
                method=method,
                path=path,
                status_code=status_code,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                duration_ms=duration_ms,
                request_size=request_size,
                response_size=response_size,
                request_id=request_id,
                query_params=query_params,
                errors=errors
            )
            
            # Log security events based on response
            self._log_security_events(
                request, status_code, method, path,
                user_id, username, ip_address, user_agent, request_id
            )
        
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request"""
        # Check for forwarded headers (load balancer/proxy)
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to client host
        return request.client.host if request.client else "unknown"
    
    def _log_security_events(
        self,
        request: Request,
        status_code: int,
        method: str,
        path: str,
        user_id: Optional[int],
        username: Optional[str],
        ip_address: str,
        user_agent: str,
        request_id: str
    ):
        """Log specific security events based on request/response"""
        
        # Authentication events
        if path == "/token" and method == "POST":
            if status_code == 200:
                self.audit_logger.log_security_event(
                    SecurityEvent.LOGIN_SUCCESS,
                    user_id=user_id,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id
                )
            elif status_code == 401:
                self.audit_logger.log_security_event(
                    SecurityEvent.LOGIN_FAILURE,
                    username=username,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    request_id=request_id,
                    severity="WARNING"
                )
        
        # Logout events
        elif path == "/auth/logout" and method == "POST" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.LOGOUT,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id
            )
        
        # Password reset events
        elif path == "/auth/forgot-password" and method == "POST" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.PASSWORD_RESET_REQUEST,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                severity="WARNING"
            )
        
        elif path == "/auth/reset-password" and method == "POST" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.PASSWORD_RESET_SUCCESS,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                severity="WARNING"
            )
        
        # Rate limiting
        elif status_code == 429:
            self.audit_logger.log_security_event(
                SecurityEvent.RATE_LIMIT_EXCEEDED,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                details={"path": path, "method": method},
                severity="WARNING"
            )
        
        # Access denied
        elif status_code == 403:
            self.audit_logger.log_security_event(
                SecurityEvent.ACCESS_DENIED,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                user_agent=user_agent,
                request_id=request_id,
                details={"path": path, "method": method},
                severity="WARNING"
            )
        
        # Character management events
        elif path.startswith("/pcs") and method == "POST" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.CHARACTER_CREATED,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                request_id=request_id
            )
        
        elif path.startswith("/pcs") and method == "PATCH" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.CHARACTER_UPDATED,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                request_id=request_id
            )
        
        elif path.startswith("/pcs") and method == "DELETE" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.CHARACTER_DELETED,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                request_id=request_id,
                severity="WARNING"
            )
        
        # Admin events
        elif path.startswith("/admin/backup") and method == "POST" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.DATABASE_BACKUP,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                request_id=request_id,
                severity="WARNING"
            )
        
        elif path.startswith("/admin/restore") and method == "POST" and status_code == 200:
            self.audit_logger.log_security_event(
                SecurityEvent.DATABASE_RESTORE,
                user_id=user_id,
                username=username,
                ip_address=ip_address,
                request_id=request_id,
                severity="CRITICAL"
            )

# Enhanced authentication middleware
class AuthMiddleware(BaseHTTPMiddleware):
    """Enhanced authentication middleware with audit logging"""
    
    def __init__(self, app, audit_logger: AuditLogger = None):
        super().__init__(app)
        self.audit_logger = audit_logger or AuditLogger()
    
    async def dispatch(self, request: Request, call_next):
        # Add user to request state if authenticated
        authorization = request.headers.get("authorization")
        if authorization:
            try:
                # Extract user information from token
                # This would integrate with your existing auth system
                pass
            except Exception as e:
                # Log authentication failure
                self.audit_logger.log_security_event(
                    SecurityEvent.LOGIN_FAILURE,
                    ip_address=request.client.host if request.client else "unknown",
                    user_agent=request.headers.get("user-agent", ""),
                    details={"error": str(e)},
                    severity="WARNING"
                )
        
        return await call_next(request)

# Global audit logger instance
global_audit_logger = AuditLogger()

def log_security_event(
    event_type: str,
    user_id: Optional[int] = None,
    username: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    severity: str = "INFO",
    request_id: Optional[str] = None
):
    """Convenience function to log security events"""
    global_audit_logger.log_security_event(
        event_type=event_type,
        user_id=user_id,
        username=username,
        ip_address=ip_address,
        user_agent=user_agent,
        details=details,
        severity=severity,
        request_id=request_id
    ) 