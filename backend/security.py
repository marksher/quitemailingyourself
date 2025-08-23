import os, secrets, hashlib
from typing import Optional
from fastapi import Request, HTTPException, Depends
from sqlalchemy import select
from .db import SessionLocal
from .models import User

def hash_api_key(seed: Optional[str] = None) -> str:
    return hashlib.sha256((seed or secrets.token_hex(32)).encode("utf-8")).hexdigest()

def current_user(request: Request) -> User:
    """Require a logged-in user via session cookie (set by Google OAuth)."""
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(401, "not authenticated")
    with SessionLocal() as s:
        user = s.get(User, user_id)
        if not user:
            raise HTTPException(401, "invalid session")
        return user

def user_from_api_key(api_key: str) -> Optional[User]:
    if not api_key:
        return None
    with SessionLocal() as s:
        u = s.execute(select(User).where(User.api_key == api_key)).scalars().first()
        return u
