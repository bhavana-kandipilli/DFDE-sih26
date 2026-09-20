import time
import logging
import json
from collections import defaultdict
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from backend.app.core.config import settings

# Setup structured logger
logger = logging.getLogger("forensic_api_audit")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(message)s'))
if not logger.handlers:
    logger.addHandler(handler)

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Injects defense-in-depth HTTP security headers into all responses:
    - MIME sniffing prevention (nosniff)
    - Clickjacking defense (DENY)
    - Cross-site scripting filtering
    - HTTP Strict Transport Security (HSTS)
    - Content Security Policy (CSP)
    - Sensitive endpoint cache prevention
    """
    SENSITIVE_PREFIXES = ("/auth", "/cases", "/tests", "/evidence", "/sync", "/dashboard")

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)

        # Baseline security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self), microphone=()"
        
        # CSP
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: blob:; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "connect-src 'self';"
        )

        # Cache control for evidentiary and analytical endpoints
        path = request.url.path
        if any(path.startswith(prefix) for prefix in self.SENSITIVE_PREFIXES):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response

class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """
    Structured JSON access logger with sensitive credential and token redaction.
    """
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        response = await call_next(request)
        duration_ms = round((time.time() - start_time) * 1000.0, 2)

        # Redact query parameters that might contain tokens
        clean_path = request.url.path

        log_payload = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "client_ip": client_ip,
            "method": request.method,
            "path": clean_path,
            "status_code": response.status_code,
            "duration_ms": duration_ms
        }
        logger.info(json.dumps(log_payload))
        return response

class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    In-memory IP rate limiter protecting forensic API against brute-force and DoS.
    """
    def __init__(self, app, requests_per_minute: int = 120):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.ip_history = defaultdict(list)

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()

        # Clean entries older than 60s
        self.ip_history[client_ip] = [t for t in self.ip_history[client_ip] if now - t < 60.0]

        if len(self.ip_history[client_ip]) >= self.requests_per_minute:
            return Response(
                content=json.dumps({"detail": "Rate limit exceeded. Please wait 60 seconds."}),
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json"
            )

        self.ip_history[client_ip].append(now)
        return await call_next(request)
