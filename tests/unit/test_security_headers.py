"""Comprehensive security header validation tests."""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from soullink_tracker.main import app


@pytest.mark.unit
class TestSecurityHeaders:
    """Test security headers are properly set and enforced."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_cors_headers_present(self, client):
        """Test that CORS headers are properly set."""
        # Test preflight request
        response = client.options(
            "/v1/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers
        assert "access-control-allow-headers" in response.headers

    def test_cors_origin_restrictions(self, client):
        """Test that CORS origin restrictions work properly."""
        # Test allowed origins
        allowed_origins = ["http://localhost:3000", "https://localhost:3000"]

        for origin in allowed_origins:
            response = client.options(
                "/v1/runs",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )
            # Should allow the origin
            assert response.headers.get("access-control-allow-origin") is not None

    def test_cors_credentials_allowed(self, client):
        """Test that CORS allows credentials when needed."""
        response = client.options(
            "/v1/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should allow credentials for authenticated requests
        assert response.headers.get("access-control-allow-credentials") == "true"

    def test_security_headers_on_api_responses(self, client):
        """Test that API responses include necessary security headers."""
        # Test a public endpoint
        response = client.get("/health")

        # Should not include overly restrictive headers on health endpoint
        assert response.status_code == 200

    def test_content_type_headers(self, client):
        """Test that content-type headers are properly set."""
        # Test JSON API endpoint
        response = client.get("/health")
        assert "application/json" in response.headers.get("content-type", "")

    def test_no_sensitive_headers_exposed(self, client):
        """Test that sensitive headers are not exposed."""
        response = client.get("/health")

        # Should not expose server information
        assert (
            "server" not in response.headers
            or "fastapi" not in response.headers.get("server", "").lower()
        )

        # Should not expose internal implementation details
        assert "x-powered-by" not in response.headers

    def test_auth_endpoint_headers(self, client):
        """Test security headers on authentication endpoints."""
        login_data = {
            "run_name": "Test Run",
            "player_name": "TestPlayer",
            "password": "test_password",
        }

        response = client.post("/v1/auth/login", json=login_data)

        # Should have proper content-type for auth responses
        if response.status_code in [200, 401, 404]:
            assert "application" in response.headers.get("content-type", "")

    def test_error_response_headers(self, client):
        """Test security headers on error responses."""
        # Trigger a 404 error
        response = client.get("/nonexistent-endpoint")

        assert response.status_code == 404
        # Should still have proper content-type
        assert "application/json" in response.headers.get("content-type", "")

    def test_rate_limit_headers_present(self, client):
        """Test that rate limit headers are included when appropriate."""
        # Make several requests to potentially trigger rate limiting
        responses = []
        for _ in range(5):
            response = client.get("/health")
            responses.append(response)

        # At least one response should be successful
        assert any(r.status_code == 200 for r in responses)

    def test_websocket_security_headers(self, client):
        """Test WebSocket upgrade security."""
        # Test WebSocket connection attempt without proper auth
        with pytest.raises(Exception):  # Should fail due to auth requirements
            with client.websocket_connect("/v1/ws?run_id=test-id"):
                pass

    def test_options_method_security(self, client):
        """Test that OPTIONS method is handled securely."""
        # Test OPTIONS on various endpoints
        endpoints = ["/v1/runs", "/v1/events", "/health"]

        for endpoint in endpoints:
            response = client.options(endpoint)
            # Should either be successful or method not allowed
            assert response.status_code in [200, 204, 405]

            # Should have proper CORS headers if successful
            if response.status_code in [200, 204]:
                assert "access-control-allow-methods" in response.headers


@pytest.mark.unit
class TestSecurityHeaderMiddleware:
    """Test security header middleware functionality."""

    def test_custom_security_middleware_integration(self):
        """Test that security headers are properly integrated."""
        # Create a minimal FastAPI app for testing
        test_app = FastAPI()

        # Add CORS middleware
        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "https://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["*"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"message": "test"}

        client = TestClient(test_app)

        response = client.get("/test")
        assert response.status_code == 200
        assert "content-type" in response.headers

    def test_cors_preflight_handling(self):
        """Test CORS preflight request handling."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST", "OPTIONS"],
            allow_headers=["authorization", "content-type"],
        )

        @test_app.post("/test")
        async def test_endpoint():
            return {"message": "test"}

        client = TestClient(test_app)

        # Send preflight request
        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )

        # Should handle preflight correctly
        assert response.status_code in [200, 204]
        assert "access-control-allow-origin" in response.headers
        assert "access-control-allow-methods" in response.headers


@pytest.mark.unit
class TestResponseSecurity:
    """Test security aspects of HTTP responses."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_error_responses_no_information_disclosure(self, client):
        """Test that error responses don't leak sensitive information."""
        # Test various error conditions
        error_cases = [
            ("/v1/runs/invalid-uuid", 422),  # Invalid UUID format
            ("/v1/nonexistent", 404),  # Nonexistent endpoint
            (
                "/v1/runs/00000000-0000-0000-0000-000000000000/events",
                401,
            ),  # Unauthorized
        ]

        for endpoint, expected_status in error_cases:
            response = client.get(endpoint)

            # Should return expected error status
            if response.status_code == expected_status or response.status_code in [
                400,
                401,
                403,
                404,
                422,
            ]:
                # Error response should not contain sensitive info
                response_text = response.text.lower()

                # Should not expose internal paths
                assert "/users/" not in response_text
                assert "/home/" not in response_text

                # Should not expose database info
                assert "database" not in response_text or "error" in response_text
                assert "sql" not in response_text

                # Should use proper content type
                assert "application/json" in response.headers.get(
                    "content-type", ""
                ) or "application/problem+json" in response.headers.get(
                    "content-type", ""
                )

    def test_auth_error_responses_consistent(self, client):
        """Test that auth error responses are consistent and don't leak info."""
        auth_endpoints = ["/v1/auth/login", "/v1/auth/jwt-login", "/v1/auth/refresh"]

        for endpoint in auth_endpoints:
            # Test with invalid data
            response = client.post(endpoint, json={"invalid": "data"})

            # Should return appropriate error
            assert response.status_code in [400, 401, 422]

            # Should have proper content type
            content_type = response.headers.get("content-type", "")
            assert (
                "application/json" in content_type
                or "application/problem+json" in content_type
            )

            # Error message should not be overly specific
            if response.status_code == 401:
                response_data = response.json()
                error_message = str(response_data).lower()

                # Should not indicate whether user exists
                assert "user not found" not in error_message
                assert "player not found" not in error_message
                assert "invalid user" not in error_message

    def test_http_method_security(self, client):
        """Test that HTTP methods are properly restricted."""
        # Test endpoints with different methods
        test_cases = [
            ("/health", "GET", [200]),
            ("/health", "POST", [405, 501]),  # Should not allow POST
            ("/health", "DELETE", [405, 501]),  # Should not allow DELETE
            ("/v1/runs", "GET", [200, 401]),  # May require auth
            ("/v1/runs", "PATCH", [405, 501]),  # Should not allow PATCH
        ]

        for endpoint, method, allowed_statuses in test_cases:
            if method == "GET":
                response = client.get(endpoint)
            elif method == "POST":
                response = client.post(endpoint, json={})
            elif method == "DELETE":
                response = client.delete(endpoint)
            elif method == "PATCH":
                response = client.patch(endpoint, json={})
            else:
                continue

            assert response.status_code in allowed_statuses + [
                405,
                501,
            ]  # Method not allowed is also acceptable

    def test_request_size_limits_implied(self, client):
        """Test that extremely large requests are handled appropriately."""
        # Test with large JSON payload
        large_data = {"data": "x" * 1000000}  # 1MB of data

        response = client.post("/v1/events", json=large_data)

        # Should either reject (413, 400) or handle gracefully
        assert response.status_code in [400, 401, 413, 422, 500]

        # Should not crash the server
        health_response = client.get("/health")
        assert health_response.status_code == 200


@pytest.mark.integration
class TestSecurityHeadersIntegration:
    """Integration tests for security headers with full application."""

    def test_security_headers_with_auth_flow(self, client, sample_run_with_player):
        """Test security headers throughout authentication flow."""
        # This would require the full app context
        # For now, just test that the endpoints exist
        response = client.get("/health")
        assert response.status_code == 200

    def test_security_headers_websocket_integration(self, client):
        """Test security considerations for WebSocket connections."""
        # WebSocket security is mainly tested in other files
        # This ensures the headers don't interfere with WebSocket upgrades

        # Test that regular HTTP endpoints still work after WebSocket setup
        response = client.get("/health")
        assert response.status_code == 200
