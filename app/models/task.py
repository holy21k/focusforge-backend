from pydantic import BaseModel, Field
from datetime import datetime, date
from typing import Optional


# -----------------------------
# CREATE - User provides date as string
# -----------------------------
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: str  # ISO date string "2026-02-08"
    due_time: Optional[str] = None  # Optional time string "14:30"
    priority: Optional[str] = "medium"  # low, medium, high


# -----------------------------
# UPDATE
# -----------------------------
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    due_date: Optional[str] = None  # ISO date string
    due_time: Optional[str] = None  # Optional time string
    priority: Optional[str] = None
    is_completed: Optional[bool] = None
    completed_at: Optional[datetime] = None
    is_missed: Optional[bool] = None
    missed_at: Optional[datetime] = None
    is_late: Optional[bool] = None
    days_late: Optional[int] = None


# -----------------------------
# RESPONSE MODEL
# -----------------------------
class Task(BaseModel):
    id: str = Field(..., description="Task ID")
    title: str
    description: Optional[str] = None
    due_date: date
    due_time: Optional[str] = None  # Optional time "14:30"
    
    # Auto-categorized by system based on due_date
    category: str = "daily"  # daily, weekly, monthly
    
    # Priority
    priority: str = "medium"
    
    # Completion tracking
    is_completed: bool = False
    completed_at: Optional[datetime] = None
    
    # Late completion tracking (for AI learning)
    is_late: bool = False
    days_late: int = 0
    
    # Missed tracking (for AI learning)
    is_missed: bool = False
    missed_at: Optional[datetime] = None
    
    user_id: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
