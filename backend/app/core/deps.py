from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    user_id = decode_token(creds.credentials, "access") if creds else None
    user = db.get(User, user_id) if user_id else None
    if not user or not user.active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "មិនទាន់ចូលប្រព័ន្ធ ឬ token ផុតកំណត់")
    return user


def require(module: str, action: str):
    """Dependency: current user must have `module.action` permission."""

    def checker(user: User = Depends(get_current_user)) -> User:
        if not user.can(module, action):
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"គ្មានសិទ្ធិ: {module}.{action}")
        return user

    return checker


def require_any(*pairs: tuple[str, str]):
    def checker(user: User = Depends(get_current_user)) -> User:
        if not any(user.can(m, a) for m, a in pairs):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "គ្មានសិទ្ធិ")
        return user

    return checker
