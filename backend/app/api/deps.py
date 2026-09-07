"""Shared FastAPI dependencies: token decoding and role-based access control."""

from __future__ import annotations

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import decode_token

bearer = HTTPBearer(auto_error=False)


def current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token")
    try:
        return decode_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token expired")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")


def require_teacher(user: dict = Depends(current_user)) -> dict:
    if user.get("role") != "teacher":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Teacher role required")
    return user


def authorise_student(user: dict, student_id: str) -> None:
    """A student may only read their own record; a teacher may read any."""
    if user.get("role") == "teacher":
        return
    if user.get("student_id") != student_id:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Students may only access their own record",
        )
