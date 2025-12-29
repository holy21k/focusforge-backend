from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional
from enum import Enum


class HabitOccurrenceStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    missed = "missed"


class HabitOccurrence(BaseModel):
    id: Optional[str] = None
    habit_id: str
    user_id: str

    scheduled_date: date

    due_start: datetime
    due_end: datetime

    status: HabitOccurrenceStatus = HabitOccurrenceStatus.pending
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True
