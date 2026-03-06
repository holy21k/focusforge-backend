from fastapi import APIRouter, HTTPException, Depends, UploadFile, File
from app.models.user import PasswordChange, PersonalizationSettings, UserUpdate
from app.services.auth_service import get_password_hash, verify_password
from app.database import get_database
from bson import ObjectId
from app.routes.auth_routes import get_current_user
import os, uuid, logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])

UPLOAD_DIR = "uploads/avatars"
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 2 * 1024 * 1024

def _get_user_or_404(current_user: str):
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return db, user

@router.put("/password")
async def change_password(password_data: PasswordChange, current_user: str = Depends(get_current_user)):
    db, user = _get_user_or_404(current_user)
    if not verify_password(password_data.current_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    db.users.update_one(
        {"_id": ObjectId(current_user)},
        {"$set": {"hashed_password": get_password_hash(password_data.new_password)}}
    )
    return {"message": "Password changed successfully"}

@router.get("/personalization")
async def get_personalization_settings(current_user: str = Depends(get_current_user)):
    _, user = _get_user_or_404(current_user)
    return {
        "theme": user.get("theme", "light"),
        "language": user.get("language", "en"),
        "notifications_enabled": user.get("notifications_enabled", True),
        "daily_reminder_time": user.get("daily_reminder_time"),
        "weekly_goal_hours": user.get("weekly_goal_hours", 10),
    }

@router.put("/personalization")
async def update_personalization_settings(settings: PersonalizationSettings, current_user: str = Depends(get_current_user)):
    db, _ = _get_user_or_404(current_user)
    update_data = {k: v for k, v in settings.model_dump().items() if v is not None}
    if update_data:
        db.users.update_one({"_id": ObjectId(current_user)}, {"$set": update_data})
    return {"message": "Settings updated successfully", "settings": update_data}

@router.get("/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    _, user = _get_user_or_404(current_user)
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "avatar_url": user.get("avatar_url"),
        "created_at": user["created_at"].isoformat() if hasattr(user["created_at"], 'isoformat') else user["created_at"],
    }

@router.put("/profile")
async def update_user_profile(update_data: UserUpdate, current_user: str = Depends(get_current_user)):
    db, _ = _get_user_or_404(current_user)
    update_dict = {}
    if update_data.username is not None:
        if db.users.find_one({"username": update_data.username, "_id": {"$ne": ObjectId(current_user)}}):
            raise HTTPException(status_code=400, detail="Username already taken")
        update_dict["username"] = update_data.username
    if update_data.email is not None:
        if db.users.find_one({"email": update_data.email, "_id": {"$ne": ObjectId(current_user)}}):
            raise HTTPException(status_code=400, detail="Email already registered")
        update_dict["email"] = update_data.email
    if update_dict:
        db.users.update_one({"_id": ObjectId(current_user)}, {"$set": update_dict})
    return {"message": "Profile updated successfully", "updated_fields": list(update_dict.keys())}

@router.post("/avatar")
async def upload_avatar(file: UploadFile = File(...), current_user: str = Depends(get_current_user)):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, or WebP allowed")
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large — max 2MB")
    ext = (file.filename or "image.jpg").rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    with open(filepath, "wb") as f:
        f.write(contents)
    avatar_url = f"/uploads/avatars/{filename}"
    db = get_database()
    db.users.update_one({"_id": ObjectId(current_user)}, {"$set": {"avatar_url": avatar_url}})
    return {"avatar_url": avatar_url, "message": "Avatar updated successfully"}