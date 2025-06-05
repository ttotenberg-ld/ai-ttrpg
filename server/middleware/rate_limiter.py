"""
Rate Limiting Middleware - Task 5.1
Implements rate limiting for API endpoints using slowapi
"""

import os
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

# Rate limit configuration from environment variables
AUTH_RATE_LIMIT = os.getenv("AUTH_RATE_LIMIT", "5/minute")  # 5 attempts per minute for auth endpoints
API_RATE_LIMIT = os.getenv("API_RATE_LIMIT", "100/minute")  # 100 requests per minute for general API
STRICT_RATE_LIMIT = os.getenv("STRICT_RATE_LIMIT", "1/minute")  # 1 request per minute for sensitive ops

def get_rate_limit_key(request: Request):
    """
    Generate rate limit key based on request details
    Uses IP address and user ID if authenticated
    """
    # Get client IP
    client_ip = get_remote_address(request)
    
    # Try to get user from request if authenticated
    user_id = None
    if hasattr(request.state, 'user') and request.state.user:
        user_id = request.state.user.id
    
    # Create compound key for better rate limiting
    if user_id:
        return f"{client_ip}:{user_id}"
    return client_ip

# Initialize limiter with Redis or in-memory storage
def create_limiter():
    """Create rate limiter instance"""
    redis_url = os.getenv("REDIS_URL")
    
    if redis_url:
        # Use Redis for production
        import redis
        from slowapi.util import get_remote_address
        
        redis_client = redis.from_url(redis_url)
        logger.info("Using Redis for rate limiting")
        
        return Limiter(
            key_func=get_rate_limit_key,
            storage_uri=redis_url,
            default_limits=[API_RATE_LIMIT]
        )
    else:
        # Use in-memory storage for development
        logger.info("Using in-memory storage for rate limiting")
        
        return Limiter(
            key_func=get_rate_limit_key,
            default_limits=[API_RATE_LIMIT]
        )

# Create global limiter instance
limiter = create_limiter()

def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    Custom rate limit exceeded handler
    Returns structured JSON response with retry information
    """
    response = JSONResponse(
        status_code=429,
        content={
            "error": "Rate limit exceeded",
            "message": f"Too many requests. Limit: {exc.detail}",
            "retry_after": exc.retry_after,
            "type": "rate_limit_error"
        },
        headers={"Retry-After": str(exc.retry_after)}
    )
    
    # Log rate limit violations
    client_ip = get_remote_address(request)
    logger.warning(
        f"Rate limit exceeded for {client_ip} on {request.url.path} - "
        f"Limit: {exc.detail}, Retry after: {exc.retry_after}s"
    )
    
    return response

class RateLimitMiddleware:
    """
    Rate limiting middleware wrapper
    Provides easy integration with FastAPI applications
    """
    
    def __init__(self, app):
        self.app = app
        # Add rate limit exception handler
        app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
        # Add SlowAPI middleware
        app.add_middleware(SlowAPIMiddleware)
    
    @staticmethod
    def get_limiter():
        """Get the global limiter instance"""
        return limiter

# Rate limit decorators for common use cases
def auth_rate_limit():
    """Rate limit decorator for authentication endpoints"""
    return limiter.limit(AUTH_RATE_LIMIT)

def api_rate_limit():
    """Rate limit decorator for general API endpoints"""
    return limiter.limit(API_RATE_LIMIT)

def strict_rate_limit():
    """Rate limit decorator for sensitive operations"""
    return limiter.limit(STRICT_RATE_LIMIT)

# Endpoint-specific rate limits
ENDPOINT_LIMITS = {
    "/token": AUTH_RATE_LIMIT,
    "/auth/login": AUTH_RATE_LIMIT,
    "/auth/register": AUTH_RATE_LIMIT,
    "/auth/forgot-password": STRICT_RATE_LIMIT,
    "/auth/reset-password": STRICT_RATE_LIMIT,
    "/users/": AUTH_RATE_LIMIT,
}

def get_endpoint_rate_limit(path: str) -> str:
    """Get rate limit for specific endpoint"""
    return ENDPOINT_LIMITS.get(path, API_RATE_LIMIT)

# Health check function
def check_rate_limiter_health():
    """Check if rate limiter is working correctly"""
    try:
        # Test the limiter storage
        if hasattr(limiter.storage, 'ping'):
            limiter.storage.ping()
        return True
    except Exception as e:
        logger.error(f"Rate limiter health check failed: {e}")
        return False 