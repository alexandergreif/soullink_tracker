"""Custom middleware for API request/response processing."""

from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..auth.rate_limiter import GlobalRateLimiter, RateLimitConfig


class ProblemDetailsException(HTTPException):
    """Enhanced HTTPException that includes RFC 9457 Problem Details."""

    def __init__(
        self,
        status_code: int,
        title: str,
        detail: Optional[str] = None,
        type_uri: Optional[str] = None,
        instance: Optional[str] = None,
        **extra_fields,
    ):
        super().__init__(status_code=status_code, detail=detail)
        self.title = title
        self.type_uri = type_uri or f"https://httpstatuses.com/{status_code}"
        self.instance = instance
        self.extra_fields = extra_fields


class ProblemDetailsMiddleware(BaseHTTPMiddleware):
    """Middleware to convert HTTP exceptions to RFC 9457 Problem Details format."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except ProblemDetailsException as exc:
            return self._create_problem_response(
                status_code=exc.status_code,
                title=exc.title,
                detail=exc.detail,
                type_uri=exc.type_uri,
                instance=exc.instance or str(request.url),
                **exc.extra_fields,
            )
        except HTTPException as exc:
            return self._create_problem_response(
                status_code=exc.status_code,
                title=self._get_default_title(exc.status_code),
                detail=exc.detail,
                instance=str(request.url),
            )
        except RequestValidationError as exc:
            return self._create_problem_response(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                title="Validation Error",
                detail="Request validation failed",
                instance=str(request.url),
                errors=exc.errors(),
            )
        except Exception:
            # Log the exception here in production
            return self._create_problem_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                title="Internal Server Error",
                detail="An unexpected error occurred",
                instance=str(request.url),
            )

    def _create_problem_response(
        self,
        status_code: int,
        title: str,
        detail: Optional[str] = None,
        type_uri: Optional[str] = None,
        instance: Optional[str] = None,
        **extra_fields,
    ) -> JSONResponse:
        """Create a JSON response in RFC 9457 Problem Details format."""
        problem = {
            "type": type_uri or f"https://httpstatuses.com/{status_code}",
            "title": title,
            "status": status_code,
        }

        if detail:
            problem["detail"] = detail
        if instance:
            problem["instance"] = instance

        # Add any extra fields
        problem.update(extra_fields)

        return JSONResponse(
            status_code=status_code,
            content=problem,
            media_type="application/problem+json",
        )

    def _get_default_title(self, status_code: int) -> str:
        """Get default title for HTTP status codes."""
        titles = {
            400: "Bad Request",
            401: "Unauthorized",
            403: "Forbidden",
            404: "Not Found",
            409: "Conflict",
            413: "Payload Too Large",
            422: "Unprocessable Entity",
            429: "Too Many Requests",
            500: "Internal Server Error",
            502: "Bad Gateway",
            503: "Service Unavailable",
        }
        return titles.get(status_code, "HTTP Error")


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to enforce request size limits."""

    def __init__(
        self,
        app: ASGIApp,
        single_request_limit: int = 16 * 1024,  # 16KB
        batch_request_limit: int = 64 * 1024,  # 64KB
    ):
        super().__init__(app)
        self.single_request_limit = single_request_limit
        self.batch_request_limit = batch_request_limit

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header first
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                length = int(content_length)
                # Determine if this is a batch request
                is_batch = request.url.path.endswith(":batch")
                limit = (
                    self.batch_request_limit if is_batch else self.single_request_limit
                )

                if length > limit:
                    raise ProblemDetailsException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        title="Request Entity Too Large",
                        detail=f"Request size {length} bytes exceeds limit of {limit} bytes",
                        type_uri="https://datatracker.ietf.org/doc/html/rfc7231#section-6.5.11",
                    )
            except ValueError:
                # Invalid Content-Length header
                raise ProblemDetailsException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    title="Bad Request",
                    detail="Invalid Content-Length header",
                )

        # For requests without Content-Length, we'll let FastAPI handle the body reading
        # and check size during processing if needed
        return await call_next(request)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate Idempotency-Key headers."""

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check idempotency for POST requests to /v1/events
        if request.method == "POST" and (
            request.url.path == "/v1/events"
            or request.url.path.startswith("/v1/events")
        ):
            idempotency_key = request.headers.get("idempotency-key")
            if idempotency_key:
                # Validate UUID v4 format
                try:
                    parsed_uuid = UUID(idempotency_key)
                    # Check if it's UUID v4 or v5 (both are RFC 4122 compliant)
                    if parsed_uuid.version not in [4, 5]:
                        raise ValueError("Not a UUID v4 or v5")
                except (ValueError, AttributeError):
                    raise ProblemDetailsException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        title="Invalid Idempotency Key",
                        detail="Idempotency-Key header must be a valid UUID v4 or v5",
                        type_uri="https://datatracker.ietf.org/doc/html/rfc4122#section-4.4",
                    )

        return await call_next(request)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add comprehensive security headers to all responses."""

    def __init__(self, app: ASGIApp, include_hsts: bool = False):
        super().__init__(app)
        self.include_hsts = include_hsts

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        # Skip actual WebSocket connections - they don't use HTTP headers the same way
        # Only skip if this is a real WebSocket upgrade request
        if "websocket" in request.headers.get("upgrade", "").lower():
            return response

        # X-Frame-Options: Prevent clickjacking attacks
        response.headers["X-Frame-Options"] = "DENY"

        # X-Content-Type-Options: Prevent MIME-type confusion attacks
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-XSS-Protection: Legacy XSS filter (modern browsers use CSP)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # X-Permitted-Cross-Domain-Policies: Restrict cross-domain policies
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Content-Security-Policy: Restrictive policy for XSS prevention
        csp_policy = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' ws: wss:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'"
        )
        response.headers["Content-Security-Policy"] = csp_policy

        # Strict-Transport-Security: Only add in HTTPS production environments
        if self.include_hsts and request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Referrer-Policy: Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy: Restrict browser features
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )

        return response


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply global rate limiting to all API endpoints."""

    def __init__(
        self,
        app: ASGIApp,
        rate_limiter: Optional[GlobalRateLimiter] = None,
        config: Optional[RateLimitConfig] = None,
    ):
        super().__init__(app)
        self.rate_limiter = rate_limiter or GlobalRateLimiter(config)

        # Endpoints to exclude from rate limiting
        self.excluded_paths = {
            "/health",
            "/ready",
            "/docs",
            "/redoc",
            "/openapi.json",
            "/favicon.ico",
        }

        # Static file prefixes to exclude
        self.excluded_prefixes = {
            "/static/",
            "/css/",
            "/js/",
        }

    def _should_apply_rate_limiting(self, path: str) -> bool:
        """Determine if rate limiting should be applied to this path."""
        # Skip excluded paths
        if path in self.excluded_paths:
            return False

        # Skip static files
        if any(path.startswith(prefix) for prefix in self.excluded_prefixes):
            return False

        # Skip WebSocket upgrade requests (handled separately)
        return True

    def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from authenticated request."""
        try:
            # Check for Authorization header
            auth_header = request.headers.get("authorization")
            if not auth_header or not auth_header.startswith("Bearer "):
                return None

            # For now, return None since user extraction would require JWT parsing
            # This can be enhanced later to extract user_id from JWT token
            # without full validation (just for rate limiting purposes)
            return None
        except Exception:
            return None

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip rate limiting for excluded paths
        if not self._should_apply_rate_limiting(request.url.path):
            return await call_next(request)

        # Skip WebSocket connections (they have different rate limiting)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)

        # Extract user ID if available
        user_id = self._extract_user_id(request)

        try:
            # Apply global rate limiting
            self.rate_limiter.check_global_rate_limit(
                request=request, endpoint_path=request.url.path, user_id=user_id
            )
        except HTTPException:
            # Re-raise HTTPException to be handled by ProblemDetailsMiddleware
            raise

        # Proceed with the request
        return await call_next(request)
