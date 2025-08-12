"""Custom middleware for API request/response processing."""

from typing import Callable, Optional
from uuid import UUID

from fastapi import Request, Response, status
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp


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
                    # Check if it's UUID v4
                    if parsed_uuid.version != 4:
                        raise ValueError("Not a UUID v4")
                except (ValueError, AttributeError):
                    raise ProblemDetailsException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        title="Invalid Idempotency Key",
                        detail="Idempotency-Key header must be a valid UUID v4",
                        type_uri="https://datatracker.ietf.org/doc/html/rfc4122#section-4.4",
                    )

        return await call_next(request)
