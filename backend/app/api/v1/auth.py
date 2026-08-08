"""Atlas account endpoints."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.api.deps import _bearer, auth_service, current_user, optional_user
from app.core.security import PASSWORD_MIN_LENGTH
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    AuthStatus,
    ChangePasswordRequest,
    LoginRequest,
    PasswordPolicy,
    RegisterRequest,
    UserRead,
)
from app.services.auth_service import AuthError, AuthService

router = APIRouter(prefix="/auth", tags=["auth"])

POLICY = PasswordPolicy(
    min_length=PASSWORD_MIN_LENGTH,
    description=(
        f"At least {PASSWORD_MIN_LENGTH} characters, including a letter, "
        "a number, and a special character."
    ),
)


@router.get("/status", response_model=AuthStatus)
def auth_status(
    user: Optional[User] = Depends(optional_user),
    svc: AuthService = Depends(auth_service),
):
    """Drives the login screen: is there an account yet, and am I signed in?"""
    return AuthStatus(
        has_accounts=svc.user_count() > 0,
        authenticated=user is not None,
        user=user,
        policy=POLICY,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, svc: AuthService = Depends(auth_service)):
    try:
        user = svc.register(
            username=payload.username,
            password=payload.password,
            email=payload.email,
            display_name=payload.display_name,
        )
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return AuthResponse(token=svc.start_session(user), user=UserRead.model_validate(user))


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, svc: AuthService = Depends(auth_service)):
    try:
        user = svc.authenticate(payload.identifier, payload.password)
    except AuthError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc
    return AuthResponse(token=svc.start_session(user), user=UserRead.model_validate(user))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    authorization: Optional[str] = Header(default=None),
    svc: AuthService = Depends(auth_service),
):
    token = _bearer(authorization)
    if token:
        svc.end_session(token)
    return None


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(current_user)):
    return user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(current_user),
    svc: AuthService = Depends(auth_service),
):
    try:
        svc.change_password(user, payload.current_password, payload.new_password)
    except AuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return None
