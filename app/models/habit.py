from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any, List
from enum import Enum


class HabitFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


# ------------------------
# HABIT MODELS
# ------------------------

class HabitBase(BaseModel):
    name: str
    description: Optional[str] = None
    frequency: HabitFrequency = HabitFrequency.daily
    target_count: int = 1
    is_active: bool = True


# FIXED: Allow frontend to send minimal data without failing
class HabitCreate(HabitBase):
    name: str  # required
    description: Optional[str] = None
    frequency: Optional[HabitFrequency] = HabitFrequency.daily
    target_count: Optional[int] = 1
    is_active: Optional[bool] = True


class HabitUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    frequency: Optional[HabitFrequency] = None
    target_count: Optional[int] = None
    is_active: Optional[bool] = None


class Habit(HabitBase):
    id: str
    user_id: str
    created_at: datetime
    current_streak: int = 0
    longest_streak: int = 0

    class Config:
        from_attributes = True


# ------------------------
# HABIT LOG MODELS
# ------------------------

class HabitLogCreate(BaseModel):
    completed: bool = True
    notes: Optional[str] = None


class HabitLog(BaseModel):
    id: Optional[Any] = None
    habit_id: str
    user_id: str
    completed_date: datetime = Field(default_factory=datetime.utcnow)
    completed: bool = True
    notes: Optional[str] = None
