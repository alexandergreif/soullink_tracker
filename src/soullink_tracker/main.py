"""Main FastAPI application for the SoulLink tracker."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api.middleware import (
    ProblemDetailsMiddleware,
    RequestSizeLimitMiddleware,
    IdempotencyMiddleware,
)
from .config import get_web_directory
from .api import runs, players, events, data, websockets, admin

# Create FastAPI app
app = FastAPI(
    title="SoulLink Tracker",
    description="Real-time tracker for 3-player Pokemon SoulLink runs in randomized HeartGold/SoulSilver",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add custom middleware in correct order (innermost first)
app.add_middleware(ProblemDetailsMiddleware)
app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)

# Add CORS middleware (configure origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global web directory - will be set by setup_static_files()
_web_directory = None


def setup_static_files():
    """Setup static file serving with portable/dev mode detection."""
    global _web_directory

    try:
        web_dir = get_web_directory()
    except Exception:
        web_dir = None

    if web_dir is None:
        # Fallback to relative path for development
        web_dir = Path(__file__).parent.parent.parent / "web"

    if web_dir and web_dir.exists():
        app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")
        _web_directory = web_dir
        return web_dir
    else:
        print(f"Warning: Web directory not found at {web_dir}")
        return None


# Setup static files - but make it safe for import
def init_static_files():
    """Initialize static files when environment is ready."""
    return setup_static_files()


# Register API routers

app.include_router(runs.router)
app.include_router(players.router)
app.include_router(events.router)
app.include_router(data.router)
app.include_router(websockets.router)
app.include_router(admin.router)


@app.get("/", include_in_schema=False)
async def root():
    """Serve web dashboard or redirect to API docs if web files not found."""
    if _web_directory:
        web_index = _web_directory / "index.html"
        if web_index.exists():
            return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/docs")


@app.get("/dashboard", include_in_schema=False)
async def dashboard(request: Request):
    """Serve the web dashboard."""
    if _web_directory:
        web_index = _web_directory / "index.html"
        if web_index.exists():
            return FileResponse(str(web_index))
    return RedirectResponse(url="/docs")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "soullink-tracker", "version": __version__}


@app.get("/ready")
async def readiness_check():
    """Readiness check endpoint that validates database connectivity and dependencies."""
    from .db.database import get_db
    from .config import get_config
    from sqlalchemy import text
    import time
    
    start_time = time.time()
    checks = {"database": False, "config": False}
    errors = []
    
    try:
        # Check database connectivity
        db = next(get_db())
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception as e:
        errors.append(f"Database check failed: {str(e)}")
    
    try:
        # Check configuration
        config = get_config()
        if config:
            checks["config"] = True
    except Exception as e:
        errors.append(f"Config check failed: {str(e)}")
    
    response_time_ms = round((time.time() - start_time) * 1000, 2)
    all_ready = all(checks.values())
    
    response = {
        "status": "ready" if all_ready else "not_ready",
        "service": "soullink-tracker",
        "version": __version__,
        "checks": checks,
        "response_time_ms": response_time_ms,
    }
    
    if errors:
        response["errors"] = errors
    
    # Return appropriate status code
    status_code = 200 if all_ready else 503
    from fastapi.responses import JSONResponse
    return JSONResponse(content=response, status_code=status_code)
