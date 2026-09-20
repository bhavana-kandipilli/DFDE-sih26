from typing import List
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.db.models import User
from backend.app.core.security import decode_access_token

security_scheme = HTTPBearer(auto_error=False)

# Standard User Roles
ROLE_FIELD_OFFICER = "FIELD_OFFICER"
ROLE_FORENSIC_ANALYST = "FORENSIC_ANALYST"
ROLE_ADMIN = "ADMIN"
ROLE_AUDITOR = "AUDITOR"
ROLE_READ_ONLY = "READ_ONLY"

ALL_ROLES = [ROLE_FIELD_OFFICER, ROLE_FORENSIC_ANALYST, ROLE_ADMIN, ROLE_AUDITOR, ROLE_READ_ONLY]

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> User:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided."
        )

    token = credentials.credentials
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token."
        )

    username: str = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload."
        )

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated."
        )

    return user

def require_roles(allowed_roles: List[str]):
    """
    Role-Based Access Control (RBAC) Dependency Factory.
    Raises 403 Forbidden if user's role is not permitted.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Action requires one of roles: {', '.join(allowed_roles)}. User role is '{current_user.role}'."
            )
        return current_user
    return role_checker
