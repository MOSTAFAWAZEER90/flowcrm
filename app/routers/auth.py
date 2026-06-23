from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.core.deps import SystemSession, require_manager
from app.schemas.auth import (
    InviteAcceptRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest, session: SystemSession) -> TokenResponse:
    user, token, expires_in = await auth_service.register(session, payload)
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)
    )


@router.post("/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SystemSession) -> TokenResponse:
    user, token, expires_in = await auth_service.authenticate(session, payload)
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)
    )


@router.post("/invite", response_model=InviteResponse, status_code=status.HTTP_201_CREATED)
async def invite(payload: InviteRequest, principal=Depends(require_manager)) -> InviteResponse:
    token, hours = await auth_service.create_invite(principal.org_id, payload)
    return InviteResponse(
        invite_token=token, email=payload.email, role=payload.role, expires_in_hours=hours
    )


@router.post("/invite/accept", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def accept_invite(payload: InviteAcceptRequest, session: SystemSession) -> TokenResponse:
    user, token, expires_in = await auth_service.accept_invite(session, payload)
    return TokenResponse(
        access_token=token, expires_in=expires_in, user=UserOut.model_validate(user)
    )
