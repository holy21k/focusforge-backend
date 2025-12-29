from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime, date
from bson import ObjectId

from app.database import get_database
from app.dependencies import get_current_user
from app.models.habit import (
    Habit,
    HabitCreate,
    HabitUpdate,
    HabitLog
)

from app.ai.habit_analyzer import analyze_habit
from app.ai.habit_coach import generate_feedback
from app.ai.habit_predictor import predict_habit_risk

router = APIRouter(prefix="/habits", tags=["habits"])


# -----------------------------
# Helpers
# -----------------------------
def serialize(doc):
    doc["id"] = str(doc["_id"])
    del doc["_id"]
    return doc


# -----------------------------
# Create Habit
# -----------------------------
@router.post("/", response_model=Habit)
async def create_habit(
    habit: HabitCreate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    habit_doc = {
        **habit.dict(),
        "user_id": current_user,
        "current_streak": 0,
        "longest_streak": 0,
        "created_at": datetime.utcnow(),
        "is_active": True,
    }

    result = db.habits.insert_one(habit_doc)
    habit_doc["_id"] = result.inserted_id

    return serialize(habit_doc)


# -----------------------------
# List Habits
# -----------------------------
@router.get("/", response_model=list[Habit])
async def get_habits(current_user: str = Depends(get_current_user)):
    db = get_database()

    habits = list(db.habits.find({"user_id": current_user}))
    return [serialize(h) for h in habits]


# -----------------------------
# Update Habit
# -----------------------------
@router.put("/{habit_id}", response_model=Habit)
async def update_habit(
    habit_id: str,
    habit: HabitUpdate,
    current_user: str = Depends(get_current_user)
):
    if not ObjectId.is_valid(habit_id):
        raise HTTPException(400, "Invalid habit id")

    db = get_database()

    update_data = habit.dict(exclude_unset=True)

    updated = db.habits.find_one_and_update(
        {"_id": ObjectId(habit_id), "user_id": current_user},
        {"$set": update_data},
        return_document=True
    )

    if not updated:
        raise HTTPException(404, "Habit not found")

    return serialize(updated)


# -----------------------------
# Log Habit Completion
# -----------------------------
@router.post("/{habit_id}/log")
async def log_habit(
    habit_id: str,
    log: HabitLog,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    habit = db.habits.find_one({
        "_id": ObjectId(habit_id),
        "user_id": current_user
    })

    if not habit:
        raise HTTPException(404, "Habit not found")

    log_doc = {
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": log.completed_date.date(),
        "status": "completed" if log.completed else "missed",
        "notes": log.notes,
        "created_at": datetime.utcnow()
    }

    db.habit_occurrences.insert_one(log_doc)

    return {"message": "Habit logged"}


# -----------------------------
# Habit Analytics (AI DATA)
# -----------------------------
@router.get("/{habit_id}/analysis")
async def habit_analysis(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    analysis = analyze_habit(habit_id, current_user)
    if not analysis:
        return {"message": "Not enough data"}

    feedback = generate_feedback(analysis)

    return {
        "analysis": analysis,
        "ai_feedback": feedback
    }


# -----------------------------
# Habit Prediction (AI)
# -----------------------------
@router.get("/{habit_id}/prediction")
async def habit_prediction(
    habit_id: str,
    current_user: str = Depends(get_current_user)
):
    prediction = predict_habit_risk(habit_id, current_user)
    return prediction
