"""Email + password auth with database-backed sessions.

Flow: signup/login verifies credentials with bcrypt, creates a UserSession
row, and sets its random token in an HTTP-only cookie. Every protected
route uses the `current_user` dependency, which looks the token up again.

Deliberately no JWT and no OAuth: a session table + cookie is the easiest
correct thing, and revocation is just deleting a row.
"""

import datetime
import secrets

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_session
from .models import User, UserSession

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "nutriterp_session"
SESSION_DAYS = 30


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _start_session(session: Session, user: User, response: Response) -> None:
    token = secrets.token_hex(32)
    session.add(
        UserSession(
            token=token,
            user_id=user.id,
            expires_at=_utcnow() + datetime.timedelta(days=SESSION_DAYS),
        )
    )
    session.commit()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,   # JavaScript cannot read it -> XSS cannot steal it
        samesite="lax",  # not sent on cross-site POSTs -> blunts CSRF
        secure=False,    # localhost is http; set True behind https in prod
        path="/",
    )


def current_user(request: Request, session: Session = Depends(get_session)) -> User:
    """Dependency for protected routes: cookie token -> User or 401."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    row = session.scalar(select(UserSession).where(UserSession.token == token))
    if row is None:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires = row.expires_at
    if expires.tzinfo is None:  # SQLite (tests) stores naive datetimes
        expires = expires.replace(tzinfo=datetime.timezone.utc)
    if expires < _utcnow():
        session.delete(row)
        session.commit()
        raise HTTPException(status_code=401, detail="Session expired")
    return session.get(User, row.user_id)


@router.post("/signup", status_code=201)
def signup(creds: Credentials, response: Response, session: Session = Depends(get_session)) -> dict:
    email = creds.email.lower()
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(email=email, password_hash=_hash(creds.password))
    session.add(user)
    session.commit()
    _start_session(session, user, response)
    return {"email": user.email}


@router.post("/login")
def login(creds: Credentials, response: Response, session: Session = Depends(get_session)) -> dict:
    user = session.scalar(select(User).where(User.email == creds.email.lower()))
    # Same error for "no such user" and "wrong password", so the endpoint
    # cannot be used to probe which emails have accounts.
    if user is None or not _verify(creds.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    _start_session(session, user, response)
    return {"email": user.email}


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session)) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if token:
        row = session.scalar(select(UserSession).where(UserSession.token == token))
        if row is not None:
            session.delete(row)
            session.commit()
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"status": "logged out"}


@router.get("/me")
def me(user: User = Depends(current_user)) -> dict:
    return {"email": user.email}
