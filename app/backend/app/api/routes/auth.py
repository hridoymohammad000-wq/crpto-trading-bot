import uuid
from typing import cast
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from app.models.auth import LoginRequest, UserResponse, ChangePasswordRequest
from app.persistence.database import PersistenceDatabase
from app.core.config import settings
from app.auth.security import get_password_hash, verify_password, create_access_token
from app.auth.deps import get_current_user
from datetime import datetime

router = APIRouter(prefix="/auth", tags=["auth"])

def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="auth_token",
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.AUTH_TOKEN_EXPIRE_MINUTES * 60,
        path="/"
    )

@router.post("/login")
async def login(req: LoginRequest, request: Request, response: Response) -> dict:
    persistence = cast(PersistenceDatabase, request.app.state.persistence_database)
    user_count = persistence.count_users()
    
    if user_count == 0:
        if not settings.APP_LOGIN_ID or not settings.APP_LOGIN_PASSWORD:
            raise HTTPException(status_code=500, detail="Server not configured for bootstrap")
        if req.login_id == settings.APP_LOGIN_ID and req.password == settings.APP_LOGIN_PASSWORD:
            user_id = str(uuid.uuid4())
            hash_pw = get_password_hash(req.password)
            user = persistence.create_user(user_id, req.login_id, hash_pw)
            token = create_access_token(user["id"])
            _set_auth_cookie(response, token)
            return {"detail": "Bootstrap successful"}
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    user = persistence.get_user_by_login_id(req.login_id)
    if not user or not verify_password(req.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if not user["is_active"]:
        raise HTTPException(status_code=401, detail="User is inactive")
        
    token = create_access_token(user["id"])
    _set_auth_cookie(response, token)
    return {"detail": "Login successful"}

@router.get("/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)) -> dict:
    return current_user

@router.post("/logout")
async def logout(response: Response) -> dict:
    response.delete_cookie(
        key="auth_token",
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return {"detail": "Logout successful"}

@router.post("/change-password")
async def change_password(
    req: ChangePasswordRequest, 
    request: Request,
    response: Response,
    current_user: dict = Depends(get_current_user)
) -> dict:
    if not verify_password(req.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password incorrect")
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password too short")
        
    persistence = cast(PersistenceDatabase, request.app.state.persistence_database)
    new_hash = get_password_hash(req.new_password)
    persistence.update_user_password(current_user["id"], new_hash)
    
    # Invalidate session
    response.delete_cookie(
        key="auth_token",
        path="/",
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )
    return {"detail": "Password changed successfully. Please login again."}
