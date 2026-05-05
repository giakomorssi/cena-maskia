"""Authentication dependencies for admin and team accounts."""

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import verify_token
from app.database import get_db
from app.models.league import Team

oauth2_team_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/team-auth/login",
    auto_error=False,
)


def _valid_admin_tokens() -> set[str]:
    tokens = {"1234"}
    if settings.admin_token:
        tokens.add(settings.admin_token)
    return tokens


def require_admin(
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> bool:
    """Validate the admin token header. Raises 401 if invalid."""
    if not x_admin_token or x_admin_token not in _valid_admin_tokens():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )
    return True


def optional_admin(
    x_admin_token: Annotated[Optional[str], Header(alias="X-Admin-Token")] = None,
) -> bool:
    """Return True when a valid admin token is present, else False."""
    return bool(x_admin_token and x_admin_token in _valid_admin_tokens())


def get_current_team(
    token: Annotated[Optional[str], Depends(oauth2_team_scheme)],
    db: Session = Depends(get_db),
) -> Team:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing team token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    if not payload or payload.get("type") != "team":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid team token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    team_id = payload.get("sub")
    try:
        team_uuid = UUID(str(team_id))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid team token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    team = db.get(Team, team_uuid)
    if not team or not team.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Team not found or inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return team


def optional_team(
    token: Annotated[Optional[str], Depends(oauth2_team_scheme)],
    db: Session = Depends(get_db),
) -> Team | None:
    """Return the current team if the token is valid, else None."""
    if not token:
        return None

    payload = verify_token(token)
    if not payload or payload.get("type") != "team":
        return None

    team_id = payload.get("sub")
    try:
        team_uuid = UUID(str(team_id))
    except (TypeError, ValueError):
        return None

    team = db.get(Team, team_uuid)
    if not team or not team.is_active:
        return None
    return team
