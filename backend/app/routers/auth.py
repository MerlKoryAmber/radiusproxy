from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import auth, crud, models
from ..database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    username: str
    password: str


class EnabledIn(BaseModel):
    enabled: bool


class PasswordIn(BaseModel):
    username: str
    new_password: str


@router.get("/status")
async def status_(
    user: str | None = Depends(auth.require_user), db: AsyncSession = Depends(get_db)
):
    return {"auth_enabled": await auth.auth_enabled(db), "user": user}


@router.post("/login")
async def login(data: LoginIn, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(models.User).where(models.User.username == data.username)
        )
    ).scalar_one_or_none()
    if not row or not auth.verify_password(data.password, row.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")
    return {"token": auth.make_token(row.username), "username": row.username}


@router.put("/settings")
async def set_enabled(
    data: EnabledIn,
    db: AsyncSession = Depends(get_db),
    user: str | None = Depends(auth.require_user),
):
    row = await db.get(models.AuthSettings, 1)
    if row is None:
        row = models.AuthSettings(id=1)
        db.add(row)
    row.enabled = data.enabled
    await crud.log(db, "update", "auth_settings", f"enabled={data.enabled}")
    await db.commit()
    return {"auth_enabled": data.enabled}


@router.put("/password")
async def change_password(
    data: PasswordIn,
    db: AsyncSession = Depends(get_db),
    user: str | None = Depends(auth.require_user),
):
    row = (
        await db.execute(
            select(models.User).where(models.User.username == data.username)
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    if len(data.new_password) < 4:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "password too short")
    row.password_hash = auth.hash_password(data.new_password)
    await crud.log(db, "update", "user_password", data.username)
    await db.commit()
    return {"ok": True}
