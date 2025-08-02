"""Main FastAPI application for the SoulLink tracker."""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .api import runs, players, events, data, websockets
from .config import get_config, get_web_directory

# Create FastAPI app
app = FastAPI(
    title="SoulLink Tracker",
    description="Real-time tracker for 3-player Pokemon SoulLink runs in randomized HeartGold/SoulSilver",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)

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
    except:
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
    return {
        "status": "healthy",
        "service": "soullink-tracker", 
        "version": __version__
    }