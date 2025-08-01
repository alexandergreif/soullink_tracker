"""Playwright configuration for end-to-end testing."""

from typing import Dict, Any

# Playwright configuration
config: Dict[str, Any] = {
    "testDir": "tests/e2e",
    "timeout": 30000,
    "expect": {
        "timeout": 5000
    },
    "fullyParallel": True,
    "forbidOnly": True,  # Fail if test.only is left in source
    "retries": 2 if "CI" in __import__("os").environ else 0,
    "workers": 1,  # Single worker for local dev to avoid conflicts
    "reporter": [
        ["html", {"open": "never"}],
        ["list"]
    ],
    "use": {
        "baseURL": "http://127.0.0.1:9000",
        "trace": "on-first-retry",
        "screenshot": "only-on-failure",
        "video": "retain-on-failure",
    },
    "projects": [
        {
            "name": "chromium",
            "use": {
                "channel": "chromium"
            }
        },
        {
            "name": "firefox", 
            "use": {
                "browserName": "firefox"
            }
        },
        {
            "name": "webkit",
            "use": {
                "browserName": "webkit"  
            }
        },
        # Mobile viewports
        {
            "name": "Mobile Chrome",
            "use": {
                "browserName": "chromium",
                "viewport": {"width": 375, "height": 667},
                "deviceScaleFactor": 2,
                "isMobile": True,
                "hasTouch": True,
            }
        }
    ],
    "webServer": {
        "command": "uvicorn src.soullink_tracker.main:app --host 127.0.0.1 --port 9000",
        "port": 9000,
        "reuseExistingServer": True,
        "timeout": 120000,
    }
}