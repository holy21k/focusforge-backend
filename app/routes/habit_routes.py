from fastapi import APIRouter, HTTPException, Depends
from app.models.habit import Habit, HabitCreate, HabitUpdate, HabitLog
from app.database import get_database
from datetime import datetime, date
from bson import ObjectId
from app.dependencies import get_current_user

router = APIRouter(prefix="/habits", tags=["habits"])

@router.get("/", response_model=list[Habit])
async def get_habits(current_user: str = Depends(get_current_user)):
    db = get_database()
    habits = list(db.habits.find({"user_id": current_user}))
    for habit in habits:
        habit["id"] = str(habit["_id"])
        del habit["_id"]  # Clean up _id
    return habits

@router.post("/", response_model=Habit)
async def create_habit(habit: HabitCreate, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    habit_dict = {
        **habit.dict(),
        "user_id": current_user,
        "current_streak": 0,
        "longest_streak": 0,
        "completed_at": None,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
        "is_active": True
    }
    
    result = db.habits.insert_one(habit_dict)
    habit_dict["id"] = str(result.inserted_id)
    del habit_dict["_id"]
    return habit_dict

@router.put("/{habit_id}", response_model=Habit)
async def update_habit(habit_id: str, habit: HabitUpdate, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit ID")
    
    existing_habit = db.habits.find_one({"_id": ObjectId(habit_id), "user_id": current_user})
    if not existing_habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    update_data = habit.dict(exclude_unset=True)
    update_data["updated_at"] = datetime.utcnow()
    
    db.habits.update_one(
        {"_id": ObjectId(habit_id), "user_id": current_user},
        {"$set": update_data}
    )
    
    updated_habit = db.habits.find_one({"_id": ObjectId(habit_id)})
    updated_habit["id"] = str(updated_habit["_id"])
    del updated_habit["_id"]
    return updated_habit

@router.delete("/{habit_id}")
async def delete_habit(habit_id: str, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit ID")
    
    result = db.habits.delete_one({"_id": ObjectId(habit_id), "user_id": current_user})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    return {"message": "Habit deleted successfully"}

@router.post("/{habit_id}/log", response_model=Habit)
async def log_habit(habit_id: str, current_user: str = Depends(get_current_user)):
    db = get_database()
    
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit ID format")
    
    habit_object_id = ObjectId(habit_id)
    habit = db.habits.find_one({"_id": habit_object_id, "user_id": current_user})
    if not habit:
        raise HTTPException(status_code=404, detail="Habit not found")
    
    today = datetime.utcnow().date()
    last_completed = habit.get("completed_at")
    
    if last_completed:
        if isinstance(last_completed, datetime):
            last_completed = last_completed.date()
    
    # Prevent double logging today (check both habit field and logs collection)
    if last_completed == today:
        raise HTTPException(status_code=400, detail="Already logged today")

    existing_log = db.habit_logs.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": {
            "$gte": datetime.combine(today, datetime.min.time()),
            "$lt": datetime.combine(today, datetime.max.time())
        }
    })
    if existing_log:
        raise HTTPException(status_code=400, detail="Already logged today")

    # Streak calculation
    current_streak = habit.get("current_streak", 0)
    longest_streak = habit.get("longest_streak", 0)

    if last_completed and (today - last_completed).days == 1:
        current_streak += 1
    else:
        current_streak = 1  # New or broken streak

    longest_streak = max(longest_streak, current_streak)

    # Insert log entry (history for analytics)
    log_entry = {
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": datetime.utcnow(),
        "completed": True,
        "logged_at": datetime.utcnow()
    }
    db.habit_logs.insert_one(log_entry)

    # Update habit document
    updates = {
        "completed_at": datetime.utcnow(),
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "updated_at": datetime.utcnow()
    }

    db.habits.update_one(
        {"_id": habit_object_id},
        {"$set": updates}
    )

    # Fetch and return updated habit
    updated_habit = db.habits.find_one({"_id": habit_object_id})
    updated_habit["id"] = str(updated_habit["_id"])
    del updated_habit["_id"]
    return updated_habit