from fastapi import APIRouter, HTTPException, Depends
from app.models.habit import Habit, HabitCreate, HabitUpdate, HabitLog
from app.database import get_database
from datetime import datetime
from bson import ObjectId
from app.dependencies import get_current_user

router = APIRouter(prefix="/habits", tags=["habits"])

@router.get("/", response_model=list[Habit])
async def get_habits(current_user: str = Depends(get_current_user)):
    db = get_database()
    habits = list(db.habits.find({"user_id": current_user}))
    for habit in habits:
        habit["id"] = str(habit["_id"])
    return habits

@router.post("/", response_model=Habit)
async def create_habit(habit: HabitCreate, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    habit_dict = {
        **habit.dict(),
        "user_id": current_user,
        "current_streak": 0,
        "longest_streak": 0,
        "created_at": datetime.now(),
        "is_active": True
    }
    
    result = db.habits.insert_one(habit_dict)
    habit_dict["id"] = str(result.inserted_id)
    return habit_dict

@router.put("/{habit_id}", response_model=Habit)
async def update_habit(habit_id: str, habit: HabitUpdate, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    existing_habit = db.habits.find_one({"_id": ObjectId(habit_id), "user_id": current_user})
    if not existing_habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    update_data = habit.dict(exclude_unset=True)
    
    db.habits.update_one(
        {"_id": ObjectId(habit_id), "user_id": current_user},
        {"$set": update_data}
    )
    
    updated_habit = db.habits.find_one({"_id": ObjectId(habit_id)})
    updated_habit["id"] = str(updated_habit["_id"])
    return updated_habit

@router.delete("/{habit_id}")
async def delete_habit(habit_id: str, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    result = db.habits.delete_one({"_id": ObjectId(habit_id), "user_id": current_user})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    return {"message": "Habit deleted successfully"}

@router.post("/{habit_id}/log")
async def log_habit(habit_id: str, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    try:
        habit_object_id = ObjectId(habit_id)
    except:
        raise HTTPException(status_code=400, detail="Invalid habit ID format")
    
    habit = db.habits.find_one({"_id": habit_object_id, "user_id": current_user})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    log_entry = {
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": datetime.now(),
        "completed": True,
        "logged_at": datetime.now()
    }
    
    db.habit_logs.insert_one(log_entry)
    
    return {"message": "Habit logged successfully"}
