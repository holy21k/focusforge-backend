from fastapi import APIRouter, Depends, HTTPException
from app.database import get_database
from app.dependencies import get_current_user
from app.models.habit import (
    Habit,
    HabitCreate,
    HabitUpdate,
    HabitLogCreate
)
from app.ai.habit_analyzer import (
    analyze_habit,
    predict_success,
    get_optimal_time,
    get_difficult_days,
    train_classifier
)
from datetime import datetime, timedelta, date
from bson import ObjectId

router = APIRouter(prefix="/habits", tags=["habits"])


def serialize(doc):
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# ------------------------
# GET HABITS
# ------------------------
@router.get("/", response_model=list[Habit])
async def get_habits(current_user: str = Depends(get_current_user)):
    db = get_database()
    # Use UTC date for consistency
    today_utc = datetime.utcnow().date()
    today_start = datetime.combine(today_utc, datetime.min.time())
    today_end = datetime.combine(today_utc, datetime.max.time())
    
    habits = list(db.habits.find({"user_id": current_user}))
    
    # Add completedToday and missedToday status for each habit
    for habit in habits:
        # Check if habit was logged today
        log = db.habit_logs.find_one({
            "habit_id": str(habit["_id"]),
            "user_id": current_user,
            "completed_date": {"$gte": today_start, "$lte": today_end}
        })
        
        if log:
            habit["completedToday"] = log.get("completed", True)
            habit["missedToday"] = not log.get("completed", True)
        else:
            habit["completedToday"] = False
            habit["missedToday"] = False
        
        # Get yesterday's status (UTC)
        yesterday_utc = today_utc - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday_utc, datetime.min.time())
        yesterday_end = datetime.combine(yesterday_utc, datetime.max.time())
        
        yesterday_log = db.habit_logs.find_one({
            "habit_id": str(habit["_id"]),
            "user_id": current_user,
            "completed_date": {"$gte": yesterday_start, "$lte": yesterday_end}
        })
        
        habit["completedYesterday"] = yesterday_log.get("completed", False) if yesterday_log else None
    
    return [serialize(h) for h in habits]


# ------------------------
# CREATE HABIT
# ------------------------
@router.post("/", response_model=Habit)
async def create_habit(
    habit: HabitCreate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    habit_dict = {
        **habit.dict(),
        "user_id": current_user,
        "created_at": datetime.utcnow(),
        "current_streak": 0,
        "longest_streak": 0
    }

    result = db.habits.insert_one(habit_dict)
    habit_dict["_id"] = result.inserted_id

    return serialize(habit_dict)


# ------------------------
# UPDATE HABIT
# ------------------------
@router.put("/{habit_id}", response_model=Habit)
async def update_habit(
    habit_id: str,
    habit: HabitUpdate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")

    update_data = habit.dict(exclude_unset=True)

    result = db.habits.find_one_and_update(
        {"_id": ObjectId(habit_id), "user_id": current_user},
        {"$set": update_data},
        return_document=True
    )

    if not result:
        raise HTTPException(status_code=404, detail="Habit not found")

    return serialize(result)


# ------------------------
# LOG HABIT - Can log for today or specific date
# ------------------------
@router.post("/{habit_id}/log")
async def log_habit(
    habit_id: str,
    completed: bool = True,
    notes: str = None,
    date_str: str = None,
    time_str: str = None,
    current_user: str = Depends(get_current_user)
):
    """
    Log a habit completion.
    - If date_str is provided, logs for that specific date
    - If date_str is not provided, logs for today (UTC)
    - time_str can be provided to set specific completion time
    """
    db = get_database()
    
    # Parse date - use provided date or today
    if date_str:
        try:
            target_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except:
            target_date = datetime.utcnow().date()
    else:
        target_date = datetime.utcnow().date()
    
    # Parse time if provided
    if time_str:
        try:
            time_parts = time_str.split(':')
            hour = int(time_parts[0])
            minute = int(time_parts[1]) if len(time_parts) > 1 else 0
            completed_at = datetime.combine(target_date, datetime.min.time().replace(hour=hour, minute=minute))
        except:
            completed_at = datetime.utcnow()
    else:
        completed_at = datetime.utcnow()
    
    target_start = datetime.combine(target_date, datetime.min.time())
    target_end = datetime.combine(target_date, datetime.max.time())
    
    # Check if log exists for target date - if yes, UPDATE; if no, INSERT
    existing_log = db.habit_logs.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": {"$gte": target_start, "$lte": target_end}
    })
    
    if existing_log:
        # UPDATE existing log
        db.habit_logs.update_one(
            {"_id": existing_log["_id"]},
            {"$set": {
                "completed": completed,
                "notes": notes,
                "completed_date": completed_at,
                "updated_at": datetime.utcnow()
            }}
        )
    else:
        # INSERT new log
        habit_log = {
            "habit_id": habit_id,
            "user_id": current_user,
            "completed_date": completed_at,
            "completed": completed,
            "notes": notes,
            "created_at": datetime.utcnow()
        }
        db.habit_logs.insert_one(habit_log)
    
    # Update habit_occurrence for AI tracking
    scheduled_datetime = datetime.combine(target_date, datetime.min.time())
    
    existing_occurrence = db.habit_occurrences.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "scheduled_date": scheduled_datetime
    })
    
    if existing_occurrence:
        # UPDATE existing occurrence
        db.habit_occurrences.update_one(
            {"_id": existing_occurrence["_id"]},
            {"$set": {
                "status": "completed" if completed else "missed",
                "completed_at": completed_at if completed else None,
                "notes": notes,
                "updated_at": datetime.utcnow()
            }}
        )
    else:
        # INSERT new occurrence
        db.habit_occurrences.insert_one({
            "habit_id": habit_id,
            "user_id": current_user,
            "scheduled_date": scheduled_datetime,
            "due_start": completed_at,
            "status": "completed" if completed else "missed",
            "completed_at": completed_at if completed else None,
            "notes": notes,
            "created_at": datetime.utcnow()
        })
    
    # Update streak only if completed
    if completed:
        habit = db.habits.find_one({"_id": ObjectId(habit_id)})
        if habit:
            current_streak = habit.get("current_streak", 0)
            longest_streak = habit.get("longest_streak", 0)
            
            new_streak = current_streak + 1
            new_longest = longest_streak
            if new_streak > longest_streak:
                new_longest = new_streak
            
            db.habits.update_one(
                {"_id": ObjectId(habit_id)},
                {"$set": {
                    "current_streak": new_streak,
                    "longest_streak": new_longest
                }}
            )
    
    return {
        "message": "Habit logged successfully", 
        "status": "logged",
        "date": str(target_date),
        "time": completed_at.isoformat()
    }


# ------------------------
# LOG HABIT FOR SPECIFIC DATE
# ------------------------
@router.post("/{habit_id}/log-date")
async def log_habit_for_date(
    habit_id: str,
    log: HabitLogCreate,
    date_str: str = None,
    current_user: str = Depends(get_current_user)
):
    """Log habit for a specific date - ALWAYS creates new entry (no updates)"""
    db = get_database()
    
    # Parse date from string (required for this endpoint)
    if date_str:
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except:
            from datetime import datetime
            target_date = datetime.utcnow().date()
    else:
        from datetime import datetime
        target_date = datetime.utcnow().date()
    
    # ALWAYS create new entry - no update logic
    # Convert date to datetime for MongoDB compatibility
    target_datetime = datetime.combine(target_date, datetime.min.time())
    
    habit_log = {
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": datetime.utcnow(),
        "completed": log.completed,
        "notes": log.notes,
    }
    db.habit_logs.insert_one(habit_log)
    
    # Create habit_occurrence for AI tracking
    db.habit_occurrences.insert_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "scheduled_date": target_datetime,
        "due_start": target_datetime,
        "status": "completed" if log.completed else "missed",
        "completed_at": datetime.utcnow(),
        "notes": log.notes
    })
    
    # Update streak if completed
    if log.completed:
        habit = db.habits.find_one({"_id": ObjectId(habit_id)})
        if habit:
            current_streak = habit.get("current_streak", 0)
            longest_streak = habit.get("longest_streak", 0)
            
            new_streak = current_streak + 1
            new_longest = longest_streak
            if new_streak > longest_streak:
                new_longest = new_streak
            
            db.habits.update_one(
                {"_id": ObjectId(habit_id)},
                {"$set": {
                    "current_streak": new_streak,
                    "longest_streak": new_longest
                }}
            )
    
    return {"message": f"Habit logged for {target_date}", "status": "logged", "date": str(target_date)}


# ------------------------
# MARK HABIT AS MISSED
# ------------------------
@router.post("/{habit_id}/missed")
async def mark_habit_missed(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    db = get_database()
    
    # Use UTC date for consistency
    today_utc = datetime.utcnow().date()
    today_start = datetime.combine(today_utc, datetime.min.time())
    today_end = datetime.combine(today_utc, datetime.max.time())
    
    # Check habit_logs first
    existing_log = db.habit_logs.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": {"$gte": today_start, "$lte": today_end}
    })
    
    if existing_log:
        # Update existing log to missed
        db.habit_logs.update_one(
            {"_id": existing_log["_id"]},
            {"$set": {"completed": False, "notes": "Marked as missed"}}
        )
    else:
        # Create a missed log
        habit_log = {
            "habit_id": habit_id,
            "user_id": current_user,
            "completed_date": datetime.utcnow(),
            "completed": False,
            "notes": "Marked as missed",
        }
        db.habit_logs.insert_one(habit_log)
    
    # Update/create habit_occurrence for AI tracking
    # Convert date to datetime for MongoDB compatibility
    scheduled_datetime = datetime.combine(today_utc, datetime.min.time())
    
    existing_occurrence = db.habit_occurrences.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "scheduled_date": scheduled_datetime
    })
    
    if existing_occurrence:
        # Update existing occurrence to missed
        db.habit_occurrences.update_one(
            {"_id": existing_occurrence["_id"]},
            {"$set": {
                "status": "missed",
                "completed_at": None,
                "notes": "Marked as missed"
            }}
        )
    else:
        # Create new occurrence record as missed
        db.habit_occurrences.insert_one({
            "habit_id": habit_id,
            "user_id": current_user,
            "scheduled_date": scheduled_datetime,
            "due_start": datetime.utcnow(),
            "status": "missed",
            "completed_at": None,
            "notes": "Marked as missed"
        })
    
    # Reset streak
    habit = db.habits.find_one({"_id": ObjectId(habit_id)})
    if habit:
        db.habits.update_one(
            {"_id": ObjectId(habit_id)},
            {"$set": {"current_streak": 0}}
        )
    
    return {"message": "Habit marked as missed", "status": "missed", "streak_reset": True}


# ------------------------
# HABIT ANALYSIS
# ------------------------
@router.get("/{habit_id}/analysis")
async def habit_analysis(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    logs = list(db.habit_logs.find({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed": True
    }))

    total = len(logs)

    return {
        "habit_id": habit_id,
        "total_completions": total,
        "consistency_score": min(100, total * 10)
    }


# ------------------------
# HABIT PREDICTION (AI/ML)
# ------------------------
@router.get("/{habit_id}/ai/predict")
async def predict_habit_success(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Predict the probability of successfully completing a habit."""
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    
    result = predict_success(habit_id, current_user)
    return result


@router.get("/{habit_id}/ai/optimal-time")
async def get_optimal_completion_time(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Find the optimal time of day to complete a habit."""
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    
    result = get_optimal_time(habit_id, current_user)
    return result


@router.get("/{habit_id}/ai/difficult-days")
async def get_hard_days(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Identify days of the week that are most difficult for a habit."""
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    
    result = get_difficult_days(habit_id, current_user)
    return result


@router.post("/{habit_id}/ai/train")
async def train_habit_model(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Train the ML model on habit occurrence data."""
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    
    result = train_classifier(habit_id=habit_id, user_id=current_user)
    
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    
    return {
        "message": "Model trained successfully",
        "train_accuracy": result["train_accuracy"],
        "test_accuracy": result["test_accuracy"],
        "samples_used": result["samples_used"]
    }


@router.get("/{habit_id}/ai/stats")
async def get_ai_stats(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get comprehensive AI analysis stats for a habit."""
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    
    analysis = analyze_habit(habit_id, current_user)
    prediction = predict_success(habit_id, current_user)
    optimal = get_optimal_time(habit_id, current_user)
    difficult = get_difficult_days(habit_id, current_user)
    
    return {
        "analysis": analysis,
        "prediction": prediction,
        "optimal_time": optimal,
        "difficult_days": difficult
    }


@router.get("/ai/welcome")
async def get_ai_welcome(current_user: str = Depends(get_current_user)):
    """Get welcome message for first-time AI users."""
    from app.ai.habit_coach import generate_ai_welcome_message
    return generate_ai_welcome_message()


@router.get("/{habit_id}/ai/suggestions")
async def get_ai_suggestions(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Get smart AI-powered suggestions based on all available data."""
    from app.ai.habit_coach import generate_smart_suggestions
    
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    
    analysis = analyze_habit(habit_id, current_user)
    prediction = predict_success(habit_id, current_user)
    optimal = get_optimal_time(habit_id, current_user)
    difficult = get_difficult_days(habit_id, current_user)
    
    if not analysis:
        return {
            "suggestions": [{
                "type": "info",
                "title": "📊 Building Your Profile",
                "message": "Start logging your habit completions to get personalized AI insights.",
                "action": "Complete this habit a few times to unlock AI predictions."
            }],
            "summary": "No data yet - start building your habit history!"
        }
    
    return generate_smart_suggestions(habit_id, current_user, analysis, prediction, optimal, difficult)


# ------------------------
# LEGACY PREDICTION ENDPOINT
# ------------------------
@router.get("/{habit_id}/prediction")
async def habit_prediction(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    """Legacy prediction endpoint - redirects to AI predict."""
    return await predict_habit_success(habit_id, current_user)
