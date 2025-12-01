from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer
from app.models.user import UserCreate, UserLogin, Token
from app.services.auth_service import get_password_hash, verify_password, create_access_token, verify_token
from app.database import get_database
from datetime import datetime
from bson import ObjectId

router = APIRouter(prefix="/auth", tags=["authentication"])
security = HTTPBearer()

def get_current_user(credentials = Depends(security)):
    payload = verify_token(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload.get("sub")

@router.post("/register", response_model=Token)
async def register(user_data: UserCreate):
    db = get_database()
    
    if db.users.find_one({"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = {
        "username": user_data.username,
        "email": user_data.email,
        "hashed_password": get_password_hash(user_data.password),
        "created_at": datetime.now()
    }
    
    result = db.users.insert_one(user_dict)
    user_id = str(result.inserted_id)
    
    access_token = create_access_token(data={"sub": user_id})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    db = get_database()
    
    user = db.users.find_one({"email": credentials.email})
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(data={"sub": str(user["_id"])})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/me")
async def get_current_user_info(current_user: str = Depends(get_current_user)):
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": str(user["_id"]), "username": user["username"], "email": user["email"]}
