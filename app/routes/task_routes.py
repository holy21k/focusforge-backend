from fastapi import APIRouter, HTTPException, Depends
from app.models.task import Task, TaskCreate, TaskUpdate
from app.database import get_database
from datetime import datetime
from bson import ObjectId
from app.dependencies import get_current_user

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.get("/", response_model=list[Task])
async def get_tasks(current_user: str = Depends(get_current_user)):
    db = get_database()
    tasks = list(db.tasks.find({"user_id": current_user}))
    for task in tasks:
        task["id"] = str(task["_id"])
    return tasks

@router.post("/", response_model=Task)
async def create_task(task: TaskCreate, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    task_dict = {
        **task.dict(),
        "user_id": current_user,
        "status": "pending",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }
    
    result = db.tasks.insert_one(task_dict)
    task_dict["id"] = str(result.inserted_id)
    return task_dict

@router.put("/{task_id}", response_model=Task)
async def update_task(task_id: str, task: TaskUpdate, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    existing_task = db.tasks.find_one({"_id": ObjectId(task_id), "user_id": current_user})
    if not existing_task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    update_data = task.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.now()
    
    db.tasks.update_one(
        {"_id": ObjectId(task_id), "user_id": current_user},
        {"$set": update_data}
    )
    
    updated_task = db.tasks.find_one({"_id": ObjectId(task_id)})
    updated_task["id"] = str(updated_task["_id"])
    return updated_task

@router.delete("/{task_id}")
async def delete_task(task_id: str, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    result = db.tasks.delete_one({"_id": ObjectId(task_id), "user_id": current_user})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
    
    return {"message": "Task deleted successfully"}
