from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from app.services.auth_service import verify_token

security = HTTPBearer()

def get_current_user(credentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload.get("sub")
