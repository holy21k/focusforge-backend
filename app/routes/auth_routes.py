from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
from app.models.user import UserCreate, UserLogin, Token, GoogleTokenRequest
from app.services.auth_service import get_password_hash, verify_password, create_access_token, verify_token
from app.database import get_database
from app.config import settings
from datetime import datetime
from bson import ObjectId
import logging
import httpx

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

def get_current_user(credentials=Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload.get("sub")

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate):
    db = get_database()
    if db.users.find_one({"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if db.users.find_one({"username": user_data.username}):
        raise HTTPException(status_code=400, detail="Username already taken")
    result = db.users.insert_one({
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "created_at": datetime.utcnow(),
        "avatar_url": None,
    })
    access_token = create_access_token(data={"sub": str(result.inserted_id)})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    db = get_database()
    user = db.users.find_one({"email": credentials.email})
    if not user or not user.get("hashed_password"):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    access_token = create_access_token(data={"sub": str(user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=Token)
async def google_login(data: GoogleTokenRequest):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {data.token}"}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")
            info = response.json()
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Google token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid Google token")

    email = info.get("email")
    name = info.get("name", email.split("@")[0] if email else "User")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    db = get_database()
    user = db.users.find_one({"email": email})
    if not user:
        result = db.users.insert_one({
            "username": name,
            "email": email,
            "hashed_password": None,
            "created_at": datetime.utcnow(),
            "avatar_url": info.get("picture"),
        })
        user_id = str(result.inserted_id)
    else:
        user_id = str(user["_id"])

    access_token = create_access_token(data={"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_current_user_info(current_user: str = Depends(get_current_user)):
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "avatar_url": user.get("avatar_url"),
    }