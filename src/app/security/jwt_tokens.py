from typing import Any, Dict, List
from jose import jwt, JWTError
from app.core.config import settings
from datetime import datetime, timedelta, timezone


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(sub: str, roles: List[str]) -> str:
    expire = _now() + timedelta(seconds=settings.access_expire_seconds)

    payload: Dict[str, Any] = {
        "sub": str(sub),
        "roles": roles,
        "type": "access",
        "iat": int(_now().timestamp()),
        "exp": int(expire.timestamp()),
    }

    token = jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_alg,
    )
    return token


def create_refresh_token(sub: str) -> str:
    expire = _now() + timedelta(seconds=settings.refresh_expire_seconds)

    payload: Dict[str, Any] = {
        "sub": str(sub),
        "type": "refresh",
        "iat": int(_now().timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_alg,
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token, settings.jwt_secret.get_secret_value(), algorithms=[settings.jwt_alg]
        )
    except JWTError as e:
        raise ValueError("invalid_token") from e
