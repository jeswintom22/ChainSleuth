"""Bearer-token authentication for state-changing API routes.

Users are configured in CHAINSLEUTH_API_USERS as comma-separated `name:role:token` entries
(role is `reviewer` or `admin`). The caller's identity always comes from the token, never the request body.
"""
from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings

ROLES = ("reviewer", "admin")
MIN_TOKEN_LENGTH = 16


@dataclass(frozen=True)
class User:
    name: str
    role: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


def parse_users(spec: str) -> list[tuple[str, str, str]]:
    users = []
    for entry in (e.strip() for e in spec.split(",")):
        if not entry:
            continue
        parts = entry.split(":", 2)
        if len(parts) != 3:
            raise ValueError("CHAINSLEUTH_API_USERS entries must look like name:role:token")
        name, role, token = (p.strip() for p in parts)
        if not name or role not in ROLES:
            raise ValueError(f"CHAINSLEUTH_API_USERS: invalid name or role in entry for {name!r}")
        if len(token) < MIN_TOKEN_LENGTH:
            raise ValueError(f"CHAINSLEUTH_API_USERS: token for {name!r} must be at least {MIN_TOKEN_LENGTH} characters")
        users.append((name, role, token))
    return users


_USERS = parse_users(settings.api_users)
_bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise _unauthorized("Authentication required")
    supplied = creds.credentials.encode()
    match = None
    for name, role, token in _USERS:  # compare against every entry to keep timing independent of position
        if hmac.compare_digest(supplied, token.encode()) and match is None:
            match = User(name, role)
    if match is None:
        raise _unauthorized("Invalid or unknown API token")
    return match


def require_admin(user: User = Depends(current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin role required")
    return user
