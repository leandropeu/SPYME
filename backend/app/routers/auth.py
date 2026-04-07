from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..schemas import AuthSessionOut, LoginRequest, UserOut
from ..services.auth import authenticate_user, get_current_user, issue_token, revoke_token


router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer(auto_error=False)


@router.post("/login", response_model=AuthSessionOut)
async def login(payload: LoginRequest, session: AsyncSession = Depends(get_db)):
    user = await authenticate_user(session, payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciais invalidas.")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Usuario inativo.")

    token, expires_at = await issue_token(session, user)
    return AuthSessionOut(token=token, expires_at=expires_at, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
async def me(current_user=Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: AsyncSession = Depends(get_db),
):
    if credentials:
        await revoke_token(session, credentials.credentials)
    return {"message": "Sessao encerrada."}
