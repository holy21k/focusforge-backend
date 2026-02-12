from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: str
    username: str
    email: str  # Changed from EmailStr to str
    hashed_password: str
    created_at: datetime
    # Personalization settings
    theme: str = "light"
    language: str = "en"
    notifications_enabled: bool = True
    daily_reminder_time: Optional[str] = None
    weekly_goal_hours: int = 10

class UserCreate(BaseModel):
    username: str
    email: str  # Changed from EmailStr to str
    password: str

class UserLogin(BaseModel):
    email: str  # Changed from EmailStr to str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

# Settings models
class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class PersonalizationSettings(BaseModel):
    theme: Optional[str] = None  # "light", "dark", "system"
    language: Optional[str] = None  # "en", "es", "fr", etc.
    notifications_enabled: Optional[bool] = None
    daily_reminder_time: Optional[str] = None  # HH:MM format
    weekly_goal_hours: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
