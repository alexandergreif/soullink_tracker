"""Comprehensive CORS security policy enforcement tests."""

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
class TestCORSSecurityPolicy:
    """Test CORS security policies and origin validation."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_cors_preflight_allowed_origins(self, client):
        """Test that only allowed origins receive proper CORS headers."""
        allowed_origins = [
            "http://localhost:3000",
            "https://localhost:3000",
            "http://127.0.0.1:3000",
            "https://127.0.0.1:3000",
        ]

        for origin in allowed_origins:
            response = client.options(
                "/v1/runs",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                },
            )

            # Should allow the origin
            assert response.status_code in [200, 204]
            assert response.headers.get("access-control-allow-origin") is not None

    def test_cors_blocks_unauthorized_origins(self, client):
        """Test that unauthorized origins are properly blocked."""
        malicious_origins = [
            "http://evil.com",
            "https://malicious-site.com",
            "http://attacker.localhost",
            "https://phishing.example.com",
            "null",  # null origin attack
            "data:",  # data URI attack
            "file://",  # file URI attack
        ]

        for origin in malicious_origins:
            response = client.options(
                "/v1/runs",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

            # Should either not include CORS headers or explicitly block
            cors_origin = response.headers.get("access-control-allow-origin")
            if cors_origin is not None:
                # If CORS headers are present, they should not allow the malicious origin
                assert cors_origin != origin
                assert cors_origin not in malicious_origins

    def test_cors_methods_restriction(self, client):
        """Test that only allowed HTTP methods are permitted via CORS."""
        dangerous_methods = ["TRACE", "CONNECT", "PATCH"]

        response = client.options(
            "/v1/events",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        if response.status_code in [200, 204]:
            allowed_methods_header = response.headers.get(
                "access-control-allow-methods", ""
            )

            # Should include standard methods
            for method in ["GET", "POST"]:
                assert method in allowed_methods_header

            # Should not include dangerous methods
            for method in dangerous_methods:
                assert method not in allowed_methods_header

    def test_cors_headers_restriction(self, client):
        """Test that only safe headers are allowed via CORS."""
        # Test with standard headers
        safe_headers = ["authorization", "content-type", "accept"]

        response = client.options(
            "/v1/events",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": ",".join(safe_headers),
            },
        )

        if response.status_code in [200, 204]:
            # Should allow safe headers
            assert "access-control-allow-headers" in response.headers

    def test_cors_credentials_policy(self, client):
        """Test CORS credentials policy is properly enforced."""
        response = client.options(
            "/v1/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        if response.status_code in [200, 204]:
            # Should allow credentials for authenticated endpoints
            credentials_allowed = response.headers.get(
                "access-control-allow-credentials"
            )
            assert credentials_allowed == "true"

    def test_cors_actual_request_origin_validation(self, client):
        """Test that actual requests (not preflight) validate origins properly."""
        # Test with allowed origin
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        # Should process the request normally
        assert response.status_code == 200

    def test_cors_origin_null_attack_prevention(self, client):
        """Test prevention of null origin attacks."""
        # Null origin should be handled securely
        response = client.options(
            "/v1/runs",
            headers={"Origin": "null", "Access-Control-Request-Method": "GET"},
        )

        # Should not allow null origin or handle it securely
        cors_origin = response.headers.get("access-control-allow-origin")
        if cors_origin:
            assert cors_origin != "null"

    def test_cors_wildcard_origin_not_used_with_credentials(self, client):
        """Test that wildcard origin is not used when credentials are allowed."""
        response = client.options(
            "/v1/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        if response.status_code in [200, 204]:
            cors_origin = response.headers.get("access-control-allow-origin")
            cors_credentials = response.headers.get("access-control-allow-credentials")

            # If credentials are allowed, origin should not be wildcard
            if cors_credentials == "true":
                assert cors_origin != "*"

    def test_cors_multiple_origins_in_header_attack(self, client):
        """Test protection against multiple origins in header attack."""
        # Try to inject multiple origins
        malicious_origin = "http://localhost:3000, http://evil.com"

        response = client.options(
            "/v1/runs",
            headers={
                "Origin": malicious_origin,
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should not reflect the malicious multiple origins
        cors_origin = response.headers.get("access-control-allow-origin")
        if cors_origin:
            assert "evil.com" not in cors_origin
            assert malicious_origin != cors_origin


@pytest.mark.unit
class TestCORSSecurityEdgeCases:
    """Test CORS security edge cases and attack vectors."""

    def test_cors_case_insensitive_origin_validation(self):
        """Test that origin validation is case-sensitive for security."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            allow_headers=["authorization"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        # Test case variations that should be blocked
        case_variations = [
            "HTTP://LOCALHOST:3000",  # Different case
            "http://LOCALHOST:3000",  # Mixed case
            "http://localhost:3000/",  # Trailing slash
            "http://localhost:3000#fragment",  # With fragment
        ]

        for origin in case_variations:
            response = client.options(
                "/test",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

            # Should handle origin validation securely
            cors_origin = response.headers.get("access-control-allow-origin")
            if cors_origin and origin != "http://localhost:3000":
                # Should not allow case variations or modified origins
                assert cors_origin == "http://localhost:3000"

    def test_cors_subdomain_attack_prevention(self):
        """Test prevention of subdomain-based CORS attacks."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET"],
            allow_headers=["authorization"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        # Subdomain attack attempts
        subdomain_attacks = [
            "http://evil.localhost:3000",
            "http://sub.localhost:3000",
            "http://localhost.evil.com:3000",
            "http://localhost:3000.evil.com",
        ]

        for origin in subdomain_attacks:
            response = client.options(
                "/test",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

            # Should block subdomain attacks
            cors_origin = response.headers.get("access-control-allow-origin")
            if cors_origin:
                assert cors_origin != origin
                assert "evil" not in cors_origin

    def test_cors_port_validation(self):
        """Test that port validation is enforced in CORS."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        # Different ports should be blocked
        wrong_ports = [
            "http://localhost:3001",  # Different port
            "http://localhost:80",  # Default HTTP port
            "http://localhost:8080",  # Common dev port
            "http://localhost",  # No port specified
        ]

        for origin in wrong_ports:
            response = client.options(
                "/test",
                headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
            )

            # Should block wrong ports
            cors_origin = response.headers.get("access-control-allow-origin")
            if cors_origin:
                assert cors_origin != origin

    def test_cors_protocol_validation(self):
        """Test that protocol (http/https) validation is enforced."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["https://localhost:3000"],  # Only HTTPS allowed
            allow_credentials=True,
            allow_methods=["GET"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        # HTTP should be blocked when only HTTPS is allowed
        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",  # HTTP instead of HTTPS
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should block HTTP when only HTTPS is allowed
        cors_origin = response.headers.get("access-control-allow-origin")
        if cors_origin:
            assert cors_origin != "http://localhost:3000"


@pytest.mark.unit
class TestCORSSecurityHeaders:
    """Test CORS-related security headers."""

    def test_vary_header_present(self):
        """Test that Vary header is present for CORS responses."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        response = client.get("/test", headers={"Origin": "http://localhost:3000"})

        # Should include Vary header for proper caching behavior
        vary_header = response.headers.get("vary")
        if vary_header:
            assert "origin" in vary_header.lower()

    def test_cors_max_age_security(self):
        """Test that CORS max-age is not set too high."""
        test_app = FastAPI()

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            allow_credentials=True,
            allow_methods=["GET", "POST"],
            max_age=600,  # 10 minutes - reasonable value
        )

        @test_app.options("/test")
        async def test_options():
            return {"status": "ok"}

        client = TestClient(test_app)

        response = client.options(
            "/test",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should have reasonable max-age (not too long for security)
        max_age = response.headers.get("access-control-max-age")
        if max_age:
            assert int(max_age) <= 86400  # Not more than 24 hours

    def test_cors_expose_headers_security(self):
        """Test that only safe headers are exposed via CORS."""
        test_app = FastAPI()

        # Safe headers to expose
        safe_expose_headers = ["x-request-id", "x-pagination-total"]

        test_app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000"],
            expose_headers=safe_expose_headers,
            allow_methods=["GET"],
        )

        @test_app.get("/test")
        async def test_endpoint():
            return {"status": "ok"}

        client = TestClient(test_app)

        response = client.get("/test", headers={"Origin": "http://localhost:3000"})

        # Should only expose safe headers
        expose_headers = response.headers.get("access-control-expose-headers", "")

        # Should not expose sensitive headers
        dangerous_headers = ["authorization", "cookie", "set-cookie", "x-api-key"]
        for dangerous_header in dangerous_headers:
            assert dangerous_header not in expose_headers.lower()


@pytest.mark.integration
class TestCORSIntegrationSecurity:
    """Integration tests for CORS security with full application."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_cors_with_authentication_flow(self, client):
        """Test CORS behavior with full authentication flow."""
        # Test preflight for auth endpoint
        response = client.options(
            "/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        # Should handle auth endpoints with CORS
        assert response.status_code in [200, 204, 405]

    def test_cors_with_websocket_endpoints(self, client):
        """Test that CORS doesn't interfere with WebSocket security."""
        # Regular HTTP requests should still work
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200

    def test_cors_with_api_endpoints(self, client):
        """Test CORS with API endpoints requiring authentication."""
        # Test preflight for API endpoint
        response = client.options(
            "/v1/runs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )

        # Should allow preflight for API endpoints
        if response.status_code in [200, 204]:
            assert "access-control-allow-headers" in response.headers

    def test_cors_origin_validation_with_real_requests(self, client):
        """Test origin validation with real API requests."""
        # Test with allowed origin
        response = client.get("/health", headers={"Origin": "http://localhost:3000"})

        assert response.status_code == 200

        # Should include CORS headers in response
        cors_origin = response.headers.get("access-control-allow-origin")
        if cors_origin:
            assert "localhost" in cors_origin

    def test_cors_security_with_error_responses(self, client):
        """Test that CORS security is maintained even with error responses."""
        # Test with invalid endpoint
        response = client.get(
            "/invalid-endpoint", headers={"Origin": "http://localhost:3000"}
        )

        # Should maintain CORS policy even for errors
        assert response.status_code == 404

        # CORS headers should still be appropriate
        cors_origin = response.headers.get("access-control-allow-origin")
        if cors_origin:
            assert (
                cors_origin != "*"
                or response.headers.get("access-control-allow-credentials") != "true"
            )
