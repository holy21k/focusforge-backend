from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class User(BaseModel):
    id: str
    username: str
    email: str  # Changed from EmailStr to str
    hashed_password: str
    created_at: datetime

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
