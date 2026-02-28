from fastapi import APIRouter, HTTPException, Depends, Query
from app.models.task import Task, TaskCreate, TaskUpdate
from app.database import get_database
from datetime import datetime, date, timedelta
from bson import ObjectId
from app.dependencies import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

def serialize_task(task: dict) -> dict:
    task["id"] = str(task["_id"])
    del task["_id"]
    return task

def categorize_task(due_date: date) -> str:
    """Auto-categorize based on due_date"""
    today = date.today()
    due = due_date
    
    # Same day = daily
    if due == today:
        return "daily"
    
    # Same week (within 7 days) = weekly
    diff = (due - today).days
    if 0 < diff <= 7:
        return "weekly"
    
    # More than 7 days = monthly
    return "monthly"

# -----------------------------
# GET TASKS - filter by date or category
# -----------------------------
@router.get("/", response_model=list[Task])
async def get_tasks(
    due_date: date = None,  # Filter by specific date
    category: str = None,   # Filter by category: daily, weekly, monthly
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    query = {"user_id": current_user}
    
    # Filter by date
    if due_date:
        start = datetime.combine(due_date, datetime.min.time())
        end = datetime.combine(due_date, datetime.max.time())
        query["due_date"] = {"$gte": start, "$lte": end}
    
    # Filter by category
    if category:
        query["category"] = category
    
    tasks = list(db.tasks.find(query).sort("due_date", 1))
    return [serialize_task(task) for task in tasks]


# -----------------------------
# GET TODAY'S TASKS
# -----------------------------
@router.get("/today", response_model=list[Task])
async def get_today_tasks(current_user: str = Depends(get_current_user)):
    """Get all tasks due today"""
    db = get_database()
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    
    tasks = list(db.tasks.find({
        "user_id": current_user,
        "due_date": {"$gte": today_start, "$lte": today_end}
    }).sort("category", 1))
    
    return [serialize_task(task) for task in tasks]


# -----------------------------
# CREATE TASK - Auto-categorize by due_date
# -----------------------------
@router.post("/", response_model=Task)
async def create_task(
    task: TaskCreate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    
    # Handle both date object and ISO string
    due_date = task.due_date
    if isinstance(due_date, str):
        # Parse ISO string to date
        due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00')).date()
    
    # Get due_time from request if provided
    due_time = getattr(task, 'due_time', None)
    priority = getattr(task, 'priority', 'medium')
    
    # Auto-categorize based on due_date
    category = categorize_task(due_date)
    
    task_dict = {
        "title": task.title,
        "description": task.description,
        "due_date": datetime.combine(due_date, datetime.min.time()),
        "due_time": due_time,
        "category": category,
        "priority": priority,
        "is_completed": False,
        "completed_at": None,
        "is_late": False,
        "days_late": 0,
        "is_missed": False,
        "missed_at": None,
        "user_id": current_user,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    
    result = db.tasks.insert_one(task_dict)
    task_dict["_id"] = result.inserted_id
    return serialize_task(task_dict)


# -----------------------------
# UPDATE TASK
# -----------------------------
@router.put("/{task_id}", response_model=Task)
async def update_task(
    task_id: str,
    task: TaskUpdate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    
    update_data = task.dict(exclude_unset=True)
    
    # If due_date changed, re-categorize
    if "due_date" in update_data:
        update_data["due_date"] = datetime.combine(update_data["due_date"], datetime.min.time())
        update_data["category"] = categorize_task(update_data["due_date"].date() if hasattr(update_data["due_date"], "date") else update_data["due_date"])
    
    update_data["updated_at"] = datetime.utcnow()
    
    result = db.tasks.find_one_and_update(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": update_data},
        return_document=True,
    )
    
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return serialize_task(result)


# -----------------------------
# COMPLETE TASK - Allow completion anytime
# -----------------------------
@router.patch("/{task_id}/complete", response_model=Task)
async def complete_task(
    task_id: str,
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    
    task = db.tasks.find_one({"_id": ObjectId(task_id), "user_id": current_user})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.get("is_completed"):
        raise HTTPException(status_code=400, detail="Task already completed")
    
    now = datetime.utcnow()
    
    # Check if late completion (for AI learning)
    today = date.today()
    task_due_date = task["due_date"]
    if hasattr(task_due_date, "date"):
        task_due_date = task_due_date.date()
    
    days_diff = (today - task_due_date).days
    is_late = days_diff > 0
    
    result = db.tasks.find_one_and_update(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": {
            "is_completed": True,
            "completed_at": now,
            "is_late": is_late,
            "days_late": days_diff if is_late else 0,
            "updated_at": now
        }},
        return_document=True,
    )
    
    return serialize_task(result)


# -----------------------------
# UNCOMPLETE / REOPEN TASK
# -----------------------------
@router.patch("/{task_id}/uncomplete", response_model=Task)
async def uncomplete_task(
    task_id: str,
    current_user: str = Depends(get_current_user)
):
    """Mark a task as not completed (reopen it)"""
    db = get_database()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    
    task = db.tasks.find_one({"_id": ObjectId(task_id), "user_id": current_user})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if not task.get("is_completed"):
        raise HTTPException(status_code=400, detail="Task is not completed")
    
    now = datetime.utcnow()
    
    result = db.tasks.find_one_and_update(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": {
            "is_completed": False,
            "completed_at": None,
            "is_late": False,
            "days_late": 0,
            "updated_at": now
        }},
        return_document=True,
    )
    
    return serialize_task(result)


# -----------------------------
# MARK TASK AS MISSED (for AI learning)
# -----------------------------
@router.patch("/{task_id}/missed", response_model=Task)
async def mark_task_missed(
    task_id: str,
    current_user: str = Depends(get_current_user)
):
    """Explicitly mark a task as missed - useful for AI to learn patterns"""
    db = get_database()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    
    task = db.tasks.find_one({"_id": ObjectId(task_id), "user_id": current_user})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.get("is_completed"):
        raise HTTPException(status_code=400, detail="Cannot mark completed task as missed")
    
    if task.get("is_missed"):
        raise HTTPException(status_code=400, detail="Task already marked as missed")
    
    now = datetime.utcnow()
    
    result = db.tasks.find_one_and_update(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": {
            "is_missed": True,
            "missed_at": now,
            "updated_at": now
        }},
        return_document=True,
    )
    
    return serialize_task(result)


# -----------------------------
# AUTO-MARK OVERDUE TASKS AS MISSED
# -----------------------------
@router.post("/auto-mark-missed")
async def auto_mark_tasks_missed(
    current_user: str = Depends(get_current_user)
):
    """Automatically mark all overdue uncompleted tasks as missed"""
    db = get_database()
    today = date.today()
    
    # Find all tasks that are:
    # 1. Not completed
    # 2. Not already marked as missed
    # 3. Due date is more than 1 day ago (past grace period)
    grace_period_end = today - timedelta(days=1)
    
    overdue_tasks = list(db.tasks.find({
        "user_id": current_user,
        "is_completed": False,
        "is_missed": {"$ne": True},
        "due_date": {"$lt": datetime.combine(grace_period_end, datetime.min.time())}
    }))
    
    now = datetime.utcnow()
    missed_count = 0
    
    for task in overdue_tasks:
        db.tasks.update_one(
            {"_id": task["_id"]},
            {"$set": {
                "is_missed": True,
                "missed_at": now,
                "updated_at": now
            }}
        )
        missed_count += 1
    
    return {
        "message": f"Marked {missed_count} tasks as missed",
        "missed_count": missed_count
    }


# -----------------------------
# GET TASK STATISTICS (for AI learning)
# -----------------------------
@router.get("/stats")
async def get_task_stats(
    start_date: date = None,
    end_date: date = None,
    current_user: str = Depends(get_current_user)
):
    """Get task completion statistics for AI analysis"""
    db = get_database()
    
    query = {"user_id": current_user}
    
    if start_date and end_date:
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        query["due_date"] = {"$gte": start, "$lte": end}
    
    tasks = list(db.tasks.find(query))
    
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("is_completed"))
    missed = sum(1 for t in tasks if t.get("is_missed"))
    pending = sum(1 for t in tasks if not t.get("is_completed") and not t.get("is_missed"))
    
    # Calculate completion rate
    completion_rate = (completed / total * 100) if total > 0 else 0
    
    # Get completion times (for analyzing best completion times)
    completion_times = []
    for t in tasks:
        if t.get("completed_at"):
            completion_times.append({
                "due_date": t["due_date"].date() if hasattr(t["due_date"], "date") else t["due_date"],
                "completed_at": t["completed_at"]
            })
    
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "missed_tasks": missed,
        "pending_tasks": pending,
        "completion_rate": round(completion_rate, 2),
        "completion_times": completion_times
    }


# -----------------------------
# GET SCHEDULE - All tasks grouped by date
# -----------------------------
@router.get("/schedule")
async def get_schedule(
    start_date: date = None,
    end_date: date = None,
    current_user: str = Depends(get_current_user)
):
    """Get all tasks grouped by due date"""
    db = get_database()
    
    query = {"user_id": current_user}
    
    # Filter by date range
    if start_date and end_date:
        start = datetime.combine(start_date, datetime.min.time())
        end = datetime.combine(end_date, datetime.max.time())
        query["due_date"] = {"$gte": start, "$lte": end}
    elif start_date:
        start = datetime.combine(start_date, datetime.min.time())
        query["due_date"] = {"$gte": start}
    elif end_date:
        end = datetime.combine(end_date, datetime.max.time())
        query["due_date"] = {"$lte": end}
    
    tasks = list(db.tasks.find(query).sort("due_date", 1))
    
    # Group by date
    schedule = {}
    for task in tasks:
        task_date = task["due_date"]
        if hasattr(task_date, "date"):
            task_date = task_date.date()
        date_str = task_date.isoformat()
        
        if date_str not in schedule:
            schedule[date_str] = []
        
        schedule[date_str].append(serialize_task(task))
    
    return {
        "schedule": schedule,
        "total_tasks": len(tasks)
    }


# -----------------------------
# DELETE TASK
# -----------------------------
@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: str = Depends(get_current_user)):
    db = get_database()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    
    result = db.tasks.delete_one({"_id": ObjectId(task_id), "user_id": current_user})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}
