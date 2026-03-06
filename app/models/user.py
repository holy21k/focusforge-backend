from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: str
    username: str
    email: EmailStr
    hashed_password: Optional[str] = None
    created_at: datetime
    theme: str = "light"
    language: str = "en"
    notifications_enabled: bool = True
    daily_reminder_time: Optional[str] = None
    weekly_goal_hours: int = 10
    avatar_url: Optional[str] = None

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    password: str

    @field_validator('username')
    @classmethod
    def username_valid(cls, v):
        if len(v.strip()) < 3:
            raise ValueError('Username must be at least 3 characters')
        if len(v) > 30:
            raise ValueError('Username must be under 30 characters')
        return v.strip()

    @field_validator('password')
    @classmethod
    def password_strong(cls, v):
        if len(v) < 6:
            raise ValueError('Password must be at least 6 characters')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class PersonalizationSettings(BaseModel):
    theme: Optional[str] = None
    language: Optional[str] = None
    notifications_enabled: Optional[bool] = None
    daily_reminder_time: Optional[str] = None
    weekly_goal_hours: Optional[int] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None

class GoogleTokenRequest(BaseModel):
    token: str