from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.database import db
from app.schemas.models import LoginRequest, RegisterRequest, TokenResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest) -> TokenResponse:
    if db.user_exists(payload.username):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already taken")
    if payload.role == "student" and not payload.student_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "student_id is required for student accounts")
    pwd_hash, salt = hash_password(payload.password)
    db.create_user(payload.username, pwd_hash, salt, payload.role,
                   payload.student_id, payload.full_name)
    token = create_access_token(payload.username, payload.role, payload.student_id)
    return TokenResponse(access_token=token, role=payload.role,
                         username=payload.username, student_id=payload.student_id)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    user = db.get_user(payload.username)
    # Same error for unknown user and wrong password - no username enumeration.
    if not user or not verify_password(payload.password, user["password_hash"], user["salt"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    token = create_access_token(user["username"], user["role"], user["student_id"])
    return TokenResponse(access_token=token, role=user["role"],
                         username=user["username"], student_id=user["student_id"])


@router.get("/me")
def me(user: dict = Depends(current_user)) -> dict:
    return {
        "username": user.get("sub"),
        "role": user.get("role"),
        "student_id": user.get("student_id"),
    }
