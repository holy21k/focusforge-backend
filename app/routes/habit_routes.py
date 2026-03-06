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
    today_utc = datetime.utcnow().date()
    today_start = datetime.combine(today_utc, datetime.min.time())
    today_end = datetime.combine(today_utc, datetime.max.time())

    habits = list(db.habits.find({"user_id": current_user}))

    for habit in habits:
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
# DELETE HABIT
# ------------------------
@router.delete("/{habit_id}")
async def delete_habit(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")

    result = db.habits.delete_one({"_id": ObjectId(habit_id), "user_id": current_user})

    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Habit not found")

    db.habit_logs.delete_many({"habit_id": habit_id})
    db.habit_occurrences.delete_many({"habit_id": habit_id})

    return {"message": "Habit deleted"}


# ------------------------
# LOG HABIT - FIXED: Blocks re-logging today
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
    db = get_database()

    # Parse target date
    if date_str:
        try:
            target_date = datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
        except:
            target_date = datetime.utcnow().date()
    else:
        target_date = datetime.utcnow().date()

    today_utc = datetime.utcnow().date()
    today_start = datetime.combine(today_utc, datetime.min.time())
    today_end = datetime.combine(today_utc, datetime.max.time())

    # 🚫 BLOCK: Prevent re-logging today if already logged
    if target_date == today_utc:
        already_logged = db.habit_logs.find_one({
            "habit_id": habit_id,
            "user_id": current_user,
            "completed_date": {"$gte": today_start, "$lte": today_end}
        })
        if already_logged:
            raise HTTPException(
                status_code=400,
                detail="Already logged today. Cannot change habit status for today."
            )

    # Parse time
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

    # Check existing log BEFORE updating
    existing_log = db.habit_logs.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": {"$gte": target_start, "$lte": target_end}
    })

    was_completed_before = existing_log and existing_log.get("completed", False)

    if existing_log:
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
        db.habit_logs.insert_one({
            "habit_id": habit_id,
            "user_id": current_user,
            "completed_date": completed_at,
            "completed": completed,
            "notes": notes,
            "created_at": datetime.utcnow()
        })

    scheduled_datetime = datetime.combine(target_date, datetime.min.time())

    existing_occurrence = db.habit_occurrences.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "scheduled_date": scheduled_datetime
    })

    if existing_occurrence:
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

    # ✅ SMART STREAK: handle complete/uncomplete correctly
    habit = db.habits.find_one({"_id": ObjectId(habit_id)})
    if habit:
        current_streak = habit.get("current_streak", 0)
        longest_streak = habit.get("longest_streak", 0)

        if completed and not was_completed_before:
            # New completion today — increment streak
            new_streak = current_streak + 1
            new_longest = max(longest_streak, new_streak)
            db.habits.update_one(
                {"_id": ObjectId(habit_id)},
                {"$set": {"current_streak": new_streak, "longest_streak": new_longest}}
            )
        elif not completed and was_completed_before:
            # Unmarking completion today — subtract streak point
            new_streak = max(0, current_streak - 1)
            db.habits.update_one(
                {"_id": ObjectId(habit_id)},
                {"$set": {"current_streak": new_streak}}
            )
        # else: no change

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
    db = get_database()

    if date_str:
        try:
            target_date = datetime.fromisoformat(date_str).date()
        except:
            target_date = datetime.utcnow().date()
    else:
        target_date = datetime.utcnow().date()

    # 🚫 BLOCK: Prevent re-logging today
    today_utc = datetime.utcnow().date()
    if target_date == today_utc:
        today_start = datetime.combine(today_utc, datetime.min.time())
        today_end = datetime.combine(today_utc, datetime.max.time())
        already_logged = db.habit_logs.find_one({
            "habit_id": habit_id,
            "user_id": current_user,
            "completed_date": {"$gte": today_start, "$lte": today_end}
        })
        if already_logged:
            raise HTTPException(
                status_code=400,
                detail="Already logged today. Cannot change habit status for today."
            )

    target_datetime = datetime.combine(target_date, datetime.min.time())

    db.habit_logs.insert_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": datetime.utcnow(),
        "completed": log.completed,
        "notes": log.notes,
    })

    db.habit_occurrences.insert_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "scheduled_date": target_datetime,
        "due_start": target_datetime,
        "status": "completed" if log.completed else "missed",
        "completed_at": datetime.utcnow(),
        "notes": log.notes
    })

    if log.completed:
        habit = db.habits.find_one({"_id": ObjectId(habit_id)})
        if habit:
            current_streak = habit.get("current_streak", 0)
            longest_streak = habit.get("longest_streak", 0)
            new_streak = current_streak + 1
            new_longest = max(longest_streak, new_streak)
            db.habits.update_one(
                {"_id": ObjectId(habit_id)},
                {"$set": {"current_streak": new_streak, "longest_streak": new_longest}}
            )

    return {"message": f"Habit logged for {target_date}", "status": "logged", "date": str(target_date)}


# ------------------------
# MARK HABIT AS MISSED - Smart streak with grace period
# ------------------------
@router.post("/{habit_id}/missed")
async def mark_habit_missed(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    today_utc = datetime.utcnow().date()
    today_start = datetime.combine(today_utc, datetime.min.time())
    today_end = datetime.combine(today_utc, datetime.max.time())

    # 🚫 BLOCK: Prevent re-missing today if already logged
    already_logged = db.habit_logs.find_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": {"$gte": today_start, "$lte": today_end}
    })
    if already_logged:
        raise HTTPException(
            status_code=400,
            detail="Already logged today. Cannot change habit status for today."
        )

    # Log the miss
    db.habit_logs.insert_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": datetime.utcnow(),
        "completed": False,
        "notes": "Marked as missed",
    })

    scheduled_datetime = datetime.combine(today_utc, datetime.min.time())
    db.habit_occurrences.insert_one({
        "habit_id": habit_id,
        "user_id": current_user,
        "scheduled_date": scheduled_datetime,
        "due_start": datetime.utcnow(),
        "status": "missed",
        "completed_at": None,
        "notes": "Marked as missed"
    })

    # ✅ SMART STREAK: grace period
    habit = db.habits.find_one({"_id": ObjectId(habit_id)})
    streak_reset = False
    new_streak = 0
    
    if habit:
        current_streak = habit.get("current_streak", 0)

        # Check yesterday
        yesterday_utc = today_utc - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday_utc, datetime.min.time())
        yesterday_end = datetime.combine(yesterday_utc, datetime.max.time())

        yesterday_log = db.habit_logs.find_one({
            "habit_id": habit_id,
            "user_id": current_user,
            "completed_date": {"$gte": yesterday_start, "$lte": yesterday_end}
        })

        yesterday_missed = yesterday_log and not yesterday_log.get("completed", True)
        yesterday_no_log = not yesterday_log

        if yesterday_missed or (yesterday_no_log and current_streak == 0):
            # 2 consecutive misses or already at 0 — reset
            new_streak = 0
            streak_reset = True
        else:
            # First miss — grace period, keep streak
            new_streak = current_streak
            streak_reset = False

        db.habits.update_one(
            {"_id": ObjectId(habit_id)},
            {"$set": {"current_streak": new_streak}}
        )

    return {
        "message": "Habit marked as missed",
        "status": "missed",
        "streak_reset": streak_reset,
        "current_streak": new_streak
    }


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
# AI ENDPOINTS
# ------------------------
@router.get("/{habit_id}/ai/predict")
async def predict_habit_success(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    result = predict_success(habit_id, current_user)
    return result


@router.get("/{habit_id}/ai/optimal-time")
async def get_optimal_completion_time(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    result = get_optimal_time(habit_id, current_user)
    return result


@router.get("/{habit_id}/ai/difficult-days")
async def get_hard_days(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(status_code=400, detail="Invalid habit id")
    result = get_difficult_days(habit_id, current_user)
    return result


@router.post("/{habit_id}/ai/train")
async def train_habit_model(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
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
    from app.ai.habit_coach import generate_ai_welcome_message
    return generate_ai_welcome_message()


@router.get("/{habit_id}/ai/suggestions")
async def get_ai_suggestions(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
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


@router.get("/{habit_id}/prediction")
async def habit_prediction(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    return await predict_habit_success(habit_id, current_user)