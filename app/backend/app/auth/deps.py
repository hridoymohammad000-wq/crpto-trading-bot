from typing import cast
from fastapi import Request, HTTPException, status
from app.persistence.database import PersistenceDatabase
from app.auth.security import decode_access_token

from app.core.config import settings

def get_current_user(request: Request) -> dict:
    token = request.cookies.get("auth_token")
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    user_id = decode_access_token(token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    persistence = cast(PersistenceDatabase, request.app.state.persistence_database)
    user = persistence.get_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    if not user["is_active"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
        )
    return user
