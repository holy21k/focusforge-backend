from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from enum import Enum


# -----------------------------
# ENUMS
# -----------------------------
class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


# -----------------------------
# BASE SHARED FIELDS
# -----------------------------
class TaskBase(BaseModel):
    title: str
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.medium
    due_date: Optional[datetime] = None


# -----------------------------
# CREATE
# -----------------------------
class TaskCreate(TaskBase):
    pass


# -----------------------------
# UPDATE
# -----------------------------
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[TaskPriority] = None
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None
    is_completed: Optional[bool] = None   # <-- added
    completed_at: Optional[datetime] = None  # <-- added


# -----------------------------
# RESPONSE MODEL
# -----------------------------
class Task(TaskBase):
    id: str = Field(..., description="Task ID")
    status: TaskStatus = TaskStatus.pending

    # NEW FIELDS (For analytics + AI + completion system)
    is_completed: bool = False
    completed_at: Optional[datetime] = None

    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
