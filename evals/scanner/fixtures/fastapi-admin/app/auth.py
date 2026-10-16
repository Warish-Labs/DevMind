from dataclasses import dataclass
from fastapi import Header, HTTPException, status

@dataclass
class CurrentUser:
    id: str
    role: str

async def get_current_user(authorization: str = Header(None)) -> CurrentUser:
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    return CurrentUser(id="usr-456", role="member")

async def require_admin(authorization: str = Header(None)) -> CurrentUser:
    user = await get_current_user(authorization)
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return user
