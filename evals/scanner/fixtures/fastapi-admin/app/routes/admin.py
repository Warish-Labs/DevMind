from fastapi import APIRouter, Depends
from ..auth import CurrentUser, get_current_user, require_admin

router = APIRouter(prefix="/admin", tags=["admin"])

# Vulnerable: administrative endpoint with authentication, but no role guard
@router.get("/users")
async def list_admin_users(user: CurrentUser = Depends(get_current_user)):
    return {"users": [{"id": "usr-1", "name": "Bob"}]}

# Safe: administrative endpoint requiring admin role
@router.delete("/users/{user_id}")
async def delete_admin_user(user_id: str, admin: CurrentUser = Depends(require_admin)):
    return {"status": "deleted", "user_id": user_id}
