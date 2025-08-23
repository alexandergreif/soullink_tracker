"""Authentication API endpoints."""

from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..db.models import Run, Player, PlayerSession
from ..auth.security import verify_password, generate_session_token
from ..auth.jwt_auth import jwt_manager
from ..auth.rate_limiter import rate_limiter
from ..config import get_config
from .schemas import LoginRequest, LoginResponse, ProblemDetails, JWTTokenResponse, TokenRefreshRequest, TokenRefreshResponse

router = APIRouter(prefix="/v1/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Login successful"},
        400: {
            "model": ProblemDetails,
            "description": "Multiple runs with same name or validation error",
        },
        401: {
            "model": ProblemDetails,
            "description": "Invalid password",
        },
        404: {
            "model": ProblemDetails, 
            "description": "Run not found or player not found",
        },
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate a player and create a session token.

    This endpoint allows players to log in with their credentials to access
    the tracker API. Players can identify their run by either run_id or run_name.
    If using run_name, it must be unique across all runs.

    Returns a session token that can be used for subsequent API requests.
    The token expires after the configured TTL period.
    
    Rate limited to prevent brute force attacks.
    """
    # Check rate limit
    rate_limiter.check_rate_limit(request, "login")
    # Resolve the run
    run: Optional[Run] = None
    
    if login_data.run_id:
        # Look up by run_id
        run = db.query(Run).filter(Run.id == login_data.run_id).first()
        if not run:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )
    elif login_data.run_name:
        # Look up by run_name - ensure uniqueness
        runs = db.query(Run).filter(
            func.lower(Run.name) == func.lower(login_data.run_name)
        ).all()
        
        if len(runs) == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Run not found",
            )
        elif len(runs) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Multiple runs found with same name. Please specify run_id.",
            )
        else:
            run = runs[0]
    else:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either run_id or run_name must be provided",
        )

    # Verify password
    if not run.password_hash or not run.password_salt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Run does not have password authentication enabled",
        )

    if not verify_password(login_data.password, run.password_salt, run.password_hash):
        # Record failed authentication attempt
        rate_limiter.record_auth_failure(request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid password",
        )

    # Find the player (case-insensitive)
    player = (
        db.query(Player)
        .filter(
            Player.run_id == run.id,
            func.lower(Player.name) == func.lower(login_data.player_name),
        )
        .first()
    )

    if not player:
        # Record failed authentication attempt
        rate_limiter.record_auth_failure(request)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found in this run",
        )

    # Generate session token
    session_token, token_hash = generate_session_token()

    # Get session TTL from config
    config = get_config()
    session_ttl_days = config.app.session_ttl_days
    expires_at = datetime.now(timezone.utc) + timedelta(days=session_ttl_days)

    # Create session record
    session = PlayerSession(
        token_hash=token_hash,
        run_id=run.id,
        player_id=player.id,
        expires_at=expires_at,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    # Record successful authentication
    rate_limiter.record_auth_success(request)

    return LoginResponse(
        session_token=session_token,
        run_id=run.id,
        player_id=player.id,
        expires_at=expires_at,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Logout successful"},
        401: {
            "model": ProblemDetails,
            "description": "Invalid or expired session token",
        },
    },
)
def logout(
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    """
    Log out a player by invalidating their session token.

    This endpoint invalidates the provided session token, requiring
    the player to log in again for subsequent API access.

    The session token should be provided in the Authorization header
    as "Bearer <token>".
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization[7:]  # Remove "Bearer " prefix

    # Validate token format
    from ..auth.security import validate_session_token_format
    validate_session_token_format(token)

    # Hash the token to find the session
    import hashlib
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    # Find and delete the session
    session = (
        db.query(PlayerSession)
        .filter(PlayerSession.token_hash == token_hash)
        .first()
    )

    if session:
        db.delete(session)
        db.commit()

    # Always return 204, even if session wasn't found
    # (Don't leak information about valid/invalid tokens)
    return None


@router.post(
    "/jwt-login",
    response_model=JWTTokenResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "JWT login successful"},
        400: {"model": ProblemDetails, "description": "Multiple runs with same name or validation error"},
        401: {"model": ProblemDetails, "description": "Invalid password"},
        404: {"model": ProblemDetails, "description": "Run not found or player not found"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def jwt_login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> JWTTokenResponse:
    """
    Authenticate a player and create JWT tokens for long sessions.

    This endpoint provides JWT-based authentication with access and refresh tokens,
    suitable for long-running sessions (2+ hours). The access token has a short
    expiration time (15 minutes by default) while the refresh token lasts longer
    (30 days by default).

    Returns both access and refresh tokens that can be used for API authentication.
    """
    # Check rate limit
    rate_limiter.check_rate_limit(request, "jwt-login")
    
    # Use the same authentication logic as regular login
    from ..auth.dependencies import authenticate_with_credentials
    
    player, run = authenticate_with_credentials(
        login_data.run_id,
        login_data.run_name,
        login_data.player_name,
        login_data.password,
        db
    )

    # Generate JWT tokens
    access_token, refresh_token, access_expires_at, refresh_expires_at = jwt_manager.create_tokens(
        player_id=player.id,
        run_id=run.id,
        player_name=player.name,
    )

    return JWTTokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        access_expires_at=access_expires_at,
        refresh_expires_at=refresh_expires_at,
        run_id=run.id,
        player_id=player.id,
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {"description": "Token refresh successful"},
        401: {"model": ProblemDetails, "description": "Invalid or expired refresh token"},
        422: {"model": ProblemDetails, "description": "Validation error"},
    },
)
def refresh_token(
    refresh_data: TokenRefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    """
    Refresh an access token using a valid refresh token.

    This endpoint allows clients to obtain a new access token without
    re-authenticating, as long as they have a valid refresh token.
    This is essential for long-running sessions where the access token
    may expire multiple times.
    """
    # Check rate limit
    rate_limiter.check_rate_limit(request, "refresh")
    
    # Generate new access token from refresh token
    new_access_token, expires_at = jwt_manager.refresh_access_token(refresh_data.refresh_token)
    
    # Record successful authentication
    rate_limiter.record_auth_success(request)
    
    return TokenRefreshResponse(
        access_token=new_access_token,
        expires_at=expires_at,
    )