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
    habits = list(db.habits.find({"user_id": current_user}))
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
# LOG HABIT (complete today)
# ------------------------
@router.post("/{habit_id}/log")
async def log_habit(
    habit_id: str,
    log: HabitLogCreate,
    current_user: str = Depends(get_current_user)
):
    db = get_database()

    habit_log = {
        "habit_id": habit_id,
        "user_id": current_user,
        "completed_date": datetime.utcnow(),
        "completed": log.completed,
        "notes": log.notes,
    }

    db.habit_logs.insert_one(habit_log)

    return {"message": "Habit logged successfully"}


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
