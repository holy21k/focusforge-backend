from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any
from enum import Enum

class HabitFrequency(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"

class Habit(BaseModel):
    id: Optional[Any] = None
    name: str
    description: Optional[str] = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_count: int = 1
    current_streak: int = 0
    longest_streak: int = 0
    user_id: str
    created_at: datetime = Field(default_factory=datetime.now)
    is_active: bool = True

    class Config:
        arbitrary_types_allowed = True

class HabitLog(BaseModel):
    habit_id: str
    user_id: str
    completed_date: datetime = Field(default_factory=datetime.now)  # FIX: Changed to datetime
    completed: bool = True
    notes: Optional[str] = None

class HabitCreate(BaseModel):
    name: str
    description: Optional[str] = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_count: int = 1

class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[HabitFrequency] = None
    target_count: Optional[int] = None
    is_active: Optional[bool] = None
