from fastapi import APIRouter, HTTPException, Depends
from app.models.user import PasswordChange, PersonalizationSettings, UserUpdate
from app.services.auth_service import get_password_hash, verify_password
from app.database import get_database
from bson import ObjectId

from app.routes.auth_routes import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])

@router.put("/password")
async def change_password(password_data: PasswordChange, current_user: str = Depends(get_current_user)):
    """Change user password"""
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Verify current password
    if not verify_password(password_data.current_password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Hash new password and update
    new_hashed_password = get_password_hash(password_data.new_password)
    db.users.update_one(
        {"_id": ObjectId(current_user)},
        {"$set": {"hashed_password": new_hashed_password}}
    )
    
    return {"message": "Password changed successfully"}

@router.get("/personalization")
async def get_personalization_settings(current_user: str = Depends(get_current_user)):
    """Get user's personalization settings"""
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "theme": user.get("theme", "light"),
        "language": user.get("language", "en"),
        "notifications_enabled": user.get("notifications_enabled", True),
        "daily_reminder_time": user.get("daily_reminder_time"),
        "weekly_goal_hours": user.get("weekly_goal_hours", 10)
    }

@router.put("/personalization")
async def update_personalization_settings(
    settings: PersonalizationSettings, 
    current_user: str = Depends(get_current_user)
):
    """Update user's personalization settings"""
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build update dict with only provided fields
    update_data = {}
    if settings.theme is not None:
        update_data["theme"] = settings.theme
    if settings.language is not None:
        update_data["language"] = settings.language
    if settings.notifications_enabled is not None:
        update_data["notifications_enabled"] = settings.notifications_enabled
    if settings.daily_reminder_time is not None:
        update_data["daily_reminder_time"] = settings.daily_reminder_time
    if settings.weekly_goal_hours is not None:
        update_data["weekly_goal_hours"] = settings.weekly_goal_hours
    
    if update_data:
        db.users.update_one(
            {"_id": ObjectId(current_user)},
            {"$set": update_data}
        )
    
    return {"message": "Settings updated successfully", "settings": update_data}

@router.get("/profile")
async def get_user_profile(current_user: str = Depends(get_current_user)):
    """Get user's profile information"""
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user["email"],
        "created_at": user["created_at"].isoformat() if hasattr(user["created_at"], 'isoformat') else user["created_at"]
    }

@router.put("/profile")
async def update_user_profile(update_data: UserUpdate, current_user: str = Depends(get_current_user)):
    """Update user's profile information"""
    db = get_database()
    user = db.users.find_one({"_id": ObjectId(current_user)})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Build update dict with only provided fields
    update_dict = {}
    if update_data.username is not None:
        # Check if username is already taken
        existing_user = db.users.find_one({"username": update_data.username, "_id": {"$ne": ObjectId(current_user)}})
        if existing_user:
            raise HTTPException(status_code=400, detail="Username already taken")
        update_dict["username"] = update_data.username
    
    if update_data.email is not None:
        # Check if email is already taken
        existing_user = db.users.find_one({"email": update_data.email, "_id": {"$ne": ObjectId(current_user)}})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        update_dict["email"] = update_data.email
    
    if update_dict:
        db.users.update_one(
            {"_id": ObjectId(current_user)},
            {"$set": update_dict}
        )
    
    return {"message": "Profile updated successfully", "updated_fields": list(update_dict.keys())}
