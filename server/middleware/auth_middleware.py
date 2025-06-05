"""
Authentication Middleware - Enhanced auth middleware with audit logging
"""

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from .request_logger import AuditLogger, SecurityEvent

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