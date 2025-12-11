from fastapi import APIRouter, HTTPException, Depends, Query
from app.models.task import Task, TaskCreate, TaskUpdate
from app.database import get_database
from datetime import datetime
from bson import ObjectId
from app.dependencies import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

def serialize_task(task: dict) -> dict:
    task["id"] = str(task["_id"])
    del task["_id"]
    return task

@router.get("/", response_model=list[Task])
async def get_tasks(
    page: int = Query(1, ge=1),
    limit: int = Query(5, ge=1, le=50),
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    skip = (page - 1) * limit
    tasks = list(
        db.tasks
        .find({"user_id": current_user})
        .skip(skip)
        .limit(limit)
    )
    return [serialize_task(task) for task in tasks]

@router.post("/", response_model=Task)
async def create_task(
    task: TaskCreate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    task_dict = {
        **task.dict(),
        "user_id": current_user,
        "status": "pending",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }
    result = db.tasks.insert_one(task_dict)
    task_dict["_id"] = result.inserted_id
    return serialize_task(task_dict)

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
    update_data["updated_at"] = datetime.utcnow()
    result = db.tasks.find_one_and_update(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": update_data},
        return_document=True,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    return serialize_task(result)

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

    # ------------------------------
    # Prevent double completion
    # ------------------------------
    if task.get("status") == "completed":
        raise HTTPException(status_code=400, detail="Task already completed")

    now = datetime.utcnow()

    # ------------------------------
    # Habit streak logic
    # ------------------------------
    current_streak = task.get("current_streak", 0)
    longest_streak = task.get("longest_streak", 0)
    times_completed = task.get("times_completed", 0)

    # If it's a habit, update streaks
    if task.get("is_habit", False):

        last_completed = task.get("completed_at")

        if last_completed:
            # If completed yesterday → streak continues
            delta_days = (now.date() - last_completed.date()).days
            if delta_days == 1:
                current_streak += 1
            else:
                # Missed → streak resets
                current_streak = 1
        else:
            current_streak = 1

        longest_streak = max(longest_streak, current_streak)

    # Normal tasks do NOT get streaks
    else:
        current_streak = task.get("current_streak", 0)
        longest_streak = task.get("longest_streak", 0)

    # ------------------------------
    # Update document
    # ------------------------------
    updates = {
        "status": "completed",
        "completed_at": now,
        "times_completed": times_completed + 1,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "updated_at": now,
    }

    updated_task = db.tasks.find_one_and_update(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": updates},
        return_document=True
    )

    return serialize_task(updated_task)

@router.delete("/{task_id}")
async def delete_task(
    task_id: str,
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    if not ObjectId.is_valid(task_id):
        raise HTTPException(status_code=400, detail="Invalid task id")
    result = db.tasks.delete_one({
        "_id": ObjectId(task_id),
        "user_id": current_user,
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"message": "Task deleted successfully"}