from pydantic import BaseModel, Field
from datetime import datetime, date, time
from typing import Optional
from enum import Enum


class HabitFrequency(str, Enum):
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"


class Habit(BaseModel):
    id: Optional[str] = None
    user_id: str

    name: str
    description: Optional[str] = None

    frequency: HabitFrequency
    target_count: int = 1

    start_date: date
    end_date: Optional[date] = None

    time_window_start: time
    time_window_end: time
    timezone: str = "Africa/Addis_Ababa"

    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True
