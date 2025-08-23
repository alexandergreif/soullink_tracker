"""JWT-based authentication with token refresh for long sessions."""

import jwt
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, Tuple
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from ..config import get_config


class JWTTokenManager:
    """Manages JWT access and refresh tokens for long-duration sessions."""

    def __init__(self):
        """Initialize JWT token manager with configuration."""
        config = get_config()
        self.secret_key = config.app.jwt_secret_key
        self.algorithm = "HS256"
        self.access_token_expires_minutes = config.app.jwt_access_token_expires_minutes
        self.refresh_token_expires_days = config.app.jwt_refresh_token_expires_days

    def create_tokens(
        self,
        player_id: UUID,
        run_id: UUID,
        player_name: str,
        additional_claims: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, str, datetime, datetime]:
        """
        Create access and refresh token pair.

        Args:
            player_id: UUID of the player
            run_id: UUID of the run
            player_name: Name of the player
            additional_claims: Optional additional claims to include

        Returns:
            Tuple of (access_token, refresh_token, access_expires_at, refresh_expires_at)
        """
        now = datetime.now(timezone.utc)
        jti = str(uuid4())  # Unique token ID

        # Access token (short-lived)
        access_expires_at = now + timedelta(minutes=self.access_token_expires_minutes)
        access_payload = {
            "sub": str(player_id),
            "run_id": str(run_id),
            "player_name": player_name,
            "iat": now,
            "exp": access_expires_at,
            "jti": jti,
            "type": "access",
        }

        if additional_claims:
            access_payload.update(additional_claims)

        access_token = jwt.encode(
            access_payload, self.secret_key, algorithm=self.algorithm
        )

        # Refresh token (long-lived)
        refresh_expires_at = now + timedelta(days=self.refresh_token_expires_days)
        refresh_payload = {
            "sub": str(player_id),
            "run_id": str(run_id),
            "player_name": player_name,
            "iat": now,
            "exp": refresh_expires_at,
            "jti": jti,
            "type": "refresh",
        }

        refresh_token = jwt.encode(
            refresh_payload, self.secret_key, algorithm=self.algorithm
        )

        return access_token, refresh_token, access_expires_at, refresh_expires_at

    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode access token.

        Args:
            token: JWT access token

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid, expired, or wrong type
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Verify token type
            if payload.get("type") != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Access token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode refresh token.

        Args:
            token: JWT refresh token

        Returns:
            Decoded token payload

        Raises:
            HTTPException: If token is invalid, expired, or wrong type
        """
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Verify token type
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return payload

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except jwt.InvalidTokenError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

    def refresh_access_token(self, refresh_token: str) -> Tuple[str, datetime]:
        """
        Create new access token from valid refresh token.

        Args:
            refresh_token: Valid JWT refresh token

        Returns:
            Tuple of (new_access_token, expires_at)

        Raises:
            HTTPException: If refresh token is invalid or expired
        """
        # Verify refresh token
        payload = self.verify_refresh_token(refresh_token)

        # Extract claims
        player_id = UUID(payload["sub"])
        run_id = UUID(payload["run_id"])
        player_name = payload["player_name"]

        # Generate new access token (keep same JTI for token family tracking)
        now = datetime.now(timezone.utc)
        access_expires_at = now + timedelta(minutes=self.access_token_expires_minutes)

        access_payload = {
            "sub": str(player_id),
            "run_id": str(run_id),
            "player_name": player_name,
            "iat": now,
            "exp": access_expires_at,
            "jti": payload["jti"],  # Keep same JTI for token family
            "type": "access",
        }

        access_token = jwt.encode(
            access_payload, self.secret_key, algorithm=self.algorithm
        )

        return access_token, access_expires_at

    def extract_player_info(self, token: str) -> Tuple[UUID, UUID, str]:
        """
        Extract player information from valid access token.

        Args:
            token: Valid JWT access token

        Returns:
            Tuple of (player_id, run_id, player_name)
        """
        payload = self.verify_access_token(token)

        player_id = UUID(payload["sub"])
        run_id = UUID(payload["run_id"])
        player_name = payload["player_name"]

        return player_id, run_id, player_name

    def get_token_expiry(self, token: str) -> datetime:
        """
        Get expiry time of token with full signature verification.

        Args:
            token: JWT token

        Returns:
            Expiry datetime

        Raises:
            HTTPException: If token is invalid, malformed, or expired
        """
        try:
            # Decode WITH signature verification - security fix for CVSS 9.1
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except (jwt.InvalidTokenError, KeyError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or malformed token",
                headers={"WWW-Authenticate": "Bearer"},
            )


# Global instance
jwt_manager = JWTTokenManager()
