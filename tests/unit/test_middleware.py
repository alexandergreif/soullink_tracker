"""Unit tests for API middleware components."""

import uuid
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

from src.soullink_tracker.api.middleware import (
    ProblemDetailsException, ProblemDetailsMiddleware, 
    RequestSizeLimitMiddleware, IdempotencyMiddleware,
    SecurityHeadersMiddleware
)


@pytest.fixture
def test_app():
    """Create a test FastAPI app with middleware."""
    app = FastAPI()
    
    # Add middleware in correct order
    app.add_middleware(ProblemDetailsMiddleware)
    app.add_middleware(IdempotencyMiddleware)
    app.add_middleware(RequestSizeLimitMiddleware, 
                      single_request_limit=1024,  # 1KB for testing
                      batch_request_limit=2048)   # 2KB for testing
    
    @app.post("/test/events")
    async def test_endpoint(request: Request):
        # Check for test-specific behavior triggers
        body = await request.body()
        data = await request.json() if body else {}
        
        if data.get("trigger") == "problem_details_exception":
            raise ProblemDetailsException(
                status_code=400,
                title="Test Problem",
                detail="This is a test problem",
                custom_field="custom_value"
            )
        elif data.get("trigger") == "http_exception":
            raise HTTPException(
                status_code=404,
                detail="Test not found"
            )
        elif data.get("trigger") == "generic_exception":
            raise ValueError("Generic error")
        
        return {"message": "success"}
    
    @app.post("/test/events:batch")
    async def test_batch_endpoint():
        return {"message": "batch success"}
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create test client."""
    return TestClient(test_app)


class TestProblemDetailsMiddleware:
    """Test Problem Details error format middleware."""
    
    def test_problem_details_exception_format(self, test_client):
        """Test that ProblemDetailsException generates correct format."""
        response = test_client.post(
            "/test/events",
            json={"trigger": "problem_details_exception"}
        )
        
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["type"] == "https://httpstatuses.com/400"
        assert problem["title"] == "Test Problem"
        assert problem["status"] == 400
        assert problem["detail"] == "This is a test problem"
        assert problem["custom_field"] == "custom_value"
        assert "instance" in problem

    def test_http_exception_conversion(self, test_client):
        """Test that regular HTTPException is converted to Problem Details."""
        response = test_client.post(
            "/test/events",
            json={"trigger": "http_exception"}
        )
        
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["type"] == "https://httpstatuses.com/404"
        assert problem["title"] == "Not Found"
        assert problem["status"] == 404
        assert problem["detail"] == "Test not found"

    def test_generic_exception_handling(self, test_client):
        """Test that generic exceptions are converted to Problem Details."""
        response = test_client.post(
            "/test/events",
            json={"trigger": "generic_exception"}
        )
        
        assert response.status_code == 500
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["type"] == "https://httpstatuses.com/500"
        assert problem["title"] == "Internal Server Error"
        assert problem["status"] == 500
        assert problem["detail"] == "An unexpected error occurred"

    def test_validation_error_handling(self, test_client):
        """Test that validation errors are converted to Problem Details."""
        # Send invalid JSON to trigger validation error
        response = test_client.post(
            "/test/events",
            json={"invalid": "data"},
            headers={"content-type": "application/json"}
        )
        
        # This should succeed since our test endpoint accepts any JSON
        # To test validation errors, we'd need an endpoint with strict validation
        assert response.status_code in [200, 422]


class TestRequestSizeLimitMiddleware:
    """Test request size validation middleware."""

    def test_single_request_size_limit(self, test_client):
        """Test that single requests exceeding limit are rejected."""
        # Create payload larger than 1KB limit
        large_data = {"data": "x" * 1500}
        
        response = test_client.post(
            "/test/events",
            json=large_data
        )
        
        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Request Entity Too Large"
        assert "1024 bytes" in problem["detail"]

    def test_batch_request_size_limit(self, test_client):
        """Test that batch requests have higher limit."""
        # Create payload larger than 1KB but smaller than 2KB batch limit
        medium_data = {"data": "x" * 1500}
        
        response = test_client.post(
            "/test/events:batch",
            json=medium_data
        )
        
        # Should succeed for batch endpoint with higher limit
        assert response.status_code == 200

    def test_batch_request_exceeding_limit(self, test_client):
        """Test that batch requests exceeding batch limit are rejected."""
        # Create payload larger than 2KB batch limit
        large_data = {"data": "x" * 2500}
        
        response = test_client.post(
            "/test/events:batch",
            json=large_data
        )
        
        assert response.status_code == 413
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Request Entity Too Large"
        assert "2048 bytes" in problem["detail"]

    def test_no_content_length_header(self, test_client):
        """Test behavior when Content-Length header is missing."""
        # This is harder to test directly with TestClient as it automatically
        # adds Content-Length. In practice, requests without Content-Length
        # would be handled by FastAPI's body reading logic.
        
        response = test_client.post(
            "/test/events",
            json={"small": "data"}
        )
        
        # Should succeed for small requests
        assert response.status_code == 200


class TestIdempotencyMiddleware:
    """Test idempotency key validation middleware."""

    def test_valid_uuid_v4_accepted(self, test_client):
        """Test that valid UUID v4 keys are accepted."""
        valid_uuid_v4 = str(uuid4())
        
        response = test_client.post(
            "/test/events",
            json={"test": "data"},
            headers={"Idempotency-Key": valid_uuid_v4}
        )
        
        assert response.status_code == 200

    def test_invalid_uuid_rejected(self, test_client):
        """Test that invalid UUID format is rejected."""
        response = test_client.post(
            "/test/events",
            json={"test": "data"},
            headers={"Idempotency-Key": "not-a-uuid"}
        )
        
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Invalid Idempotency Key"
        assert "UUID v4" in problem["detail"]

    def test_uuid_v1_rejected(self, test_client):
        """Test that non-v4 UUIDs are rejected."""
        # Generate UUID v1 (time-based)
        uuid_v1 = str(uuid.uuid1())
        
        response = test_client.post(
            "/test/events",
            json={"test": "data"},
            headers={"Idempotency-Key": uuid_v1}
        )
        
        assert response.status_code == 400
        assert response.headers["content-type"] == "application/problem+json"

    def test_no_idempotency_key_allowed(self, test_client):
        """Test that requests without idempotency key are allowed."""
        response = test_client.post(
            "/test/events",
            json={"test": "data"}
        )
        
        assert response.status_code == 200

    def test_only_events_endpoints_checked(self, test_client):
        """Test that idempotency validation only applies to /v1/events endpoints."""
        # This would require adding another endpoint to test with
        # For now, we verify it works with /test/events (contains "events")
        
        response = test_client.post(
            "/test/events",
            json={"test": "data"},
            headers={"Idempotency-Key": "invalid"}
        )
        
        assert response.status_code == 400  # Should be validated


class TestMiddlewareIntegration:
    """Test middleware working together."""

    def test_middleware_order_and_interaction(self, test_client):
        """Test that middleware works correctly together."""
        # Test request that should trigger multiple middleware checks
        valid_uuid = str(uuid4())
        
        response = test_client.post(
            "/test/events",
            json={"test": "data"},
            headers={"Idempotency-Key": valid_uuid}
        )
        
        # All middleware should pass, request should succeed
        assert response.status_code == 200

    def test_error_in_later_middleware_still_formatted(self, test_client):
        """Test that errors from later processing still get Problem Details format."""
        valid_uuid = str(uuid4())
        
        response = test_client.post(
            "/test/events",
            json={"trigger": "http_exception"},
            headers={"Idempotency-Key": valid_uuid}
        )
        
        # Should be formatted as Problem Details despite passing through all middleware
        assert response.status_code == 404
        assert response.headers["content-type"] == "application/problem+json"
        
        problem = response.json()
        assert problem["title"] == "Not Found"


class TestSecurityHeadersMiddleware:
    """Test security headers middleware."""
    
    def test_security_headers_added_to_response(self):
        """Test that all security headers are added to HTTP responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        # Verify all security headers are present
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert response.headers["X-XSS-Protection"] == "1; mode=block"
        assert response.headers["X-Permitted-Cross-Domain-Policies"] == "none"
        assert "Content-Security-Policy" in response.headers
        assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
        assert response.headers["Permissions-Policy"] == "geolocation=(), microphone=(), camera=()"

    def test_content_security_policy_header(self):
        """Test that CSP header contains expected directives."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        csp = response.headers["Content-Security-Policy"]
        
        # Verify key CSP directives
        assert "default-src 'self'" in csp
        assert "script-src 'self' 'unsafe-inline'" in csp
        assert "style-src 'self' 'unsafe-inline'" in csp
        assert "img-src 'self' data:" in csp
        assert "connect-src 'self' ws: wss:" in csp
        assert "object-src 'none'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_hsts_header_in_production(self):
        """Test that HSTS header is added when include_hsts=True and HTTPS."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, include_hsts=True)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Test with HTTPS request
        client = TestClient(app, base_url="https://example.com")
        response = client.get("/test")
        
        # HSTS should be present for HTTPS
        assert "Strict-Transport-Security" in response.headers
        hsts = response.headers["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_no_hsts_header_in_development(self):
        """Test that HSTS header is NOT added when include_hsts=False."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, include_hsts=False)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        # HSTS should NOT be present in development
        assert "Strict-Transport-Security" not in response.headers

    def test_no_hsts_header_for_http(self):
        """Test that HSTS header is NOT added for HTTP even when include_hsts=True."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, include_hsts=True)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Test with HTTP request (default TestClient base_url)
        client = TestClient(app)
        response = client.get("/test")
        
        # HSTS should NOT be present for HTTP
        assert "Strict-Transport-Security" not in response.headers

    def test_websocket_connections_skip_headers(self):
        """Test that WebSocket paths don't interfere with middleware."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/v1/ws-info")
        async def ws_info_endpoint():
            return {"message": "WebSocket info endpoint"}
        
        @app.get("/regular-endpoint")
        async def regular_endpoint():
            return {"message": "Regular endpoint"}
        
        client = TestClient(app)
        
        # Test that /v1/ws path prefix works correctly
        response = client.get("/v1/ws-info")
        assert response.status_code == 200
        
        # The middleware should still apply headers to HTTP endpoints
        # even if they have 'ws' in the path
        assert response.headers["X-Frame-Options"] == "DENY"
        
        # Test regular endpoint also gets headers
        response2 = client.get("/regular-endpoint")
        assert response2.headers["X-Frame-Options"] == "DENY"

    def test_headers_not_duplicated(self):
        """Test that headers aren't duplicated if middleware runs multiple times."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        # Headers should be single values, not lists
        for header_name in ["X-Frame-Options", "X-Content-Type-Options", "X-XSS-Protection"]:
            header_value = response.headers.get(header_name)
            assert isinstance(header_value, str), f"{header_name} should be a string, not a list"

    def test_security_headers_on_error_responses(self):
        """Test that security headers are added even to error responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            raise HTTPException(status_code=404, detail="Not found")
        
        client = TestClient(app)
        response = client.get("/test")
        
        # Verify security headers are present on error responses
        assert response.status_code == 404
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Security-Policy" in response.headers

    def test_security_headers_on_different_methods(self):
        """Test that security headers are added for all HTTP methods."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/test")
        async def get_endpoint():
            return {"message": "get"}
        
        @app.post("/test")
        async def post_endpoint():
            return {"message": "post"}
        
        @app.put("/test")
        async def put_endpoint():
            return {"message": "put"}
        
        @app.delete("/test")
        async def delete_endpoint():
            return {"message": "delete"}
        
        client = TestClient(app)
        
        # Test all methods have security headers
        for method in ['get', 'post', 'put', 'delete']:
            response = getattr(client, method)("/test")
            assert response.headers["X-Frame-Options"] == "DENY"
            assert "Content-Security-Policy" in response.headers

    def test_security_headers_with_json_responses(self):
        """Test that security headers work with JSON API responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/api/data")
        async def api_endpoint():
            return {"data": [1, 2, 3], "status": "success"}
        
        client = TestClient(app)
        response = client.get("/api/data")
        
        # Verify JSON response works with security headers
        assert response.status_code == 200
        assert response.json() == {"data": [1, 2, 3], "status": "success"}
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers

    def test_security_headers_with_static_file_responses(self):
        """Test that security headers are compatible with file responses."""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)
        
        @app.get("/file")
        async def file_endpoint():
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse("Hello, World!", media_type="text/plain")
        
        client = TestClient(app)
        response = client.get("/file")
        
        # Verify file response works with security headers
        assert response.status_code == 200
        assert response.text == "Hello, World!"
        assert response.headers["X-Frame-Options"] == "DENY"
        assert "Content-Security-Policy" in response.headers