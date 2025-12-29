from app.database import get_database
from datetime import datetime, timedelta


def predict_habit_risk(habit_id: str, user_id: str):
    """
    Predicts risk of habit failure based on recent behavior.
    Returns: LOW | MEDIUM | HIGH
    """

    db = get_database()

    last_14_days = datetime.utcnow() - timedelta(days=14)

    occurrences = list(
        db.habit_occurrences.find({
            "habit_id": habit_id,
            "user_id": user_id,
            "scheduled_date": {"$gte": last_14_days}
        }).sort("scheduled_date", -1)
    )

    if len(occurrences) < 5:
        return {
            "risk": "UNKNOWN",
            "reason": "Not enough data"
        }

    missed = sum(1 for o in occurrences if o["status"] == "missed")
    completed = sum(1 for o in occurrences if o["status"] == "completed")

    miss_ratio = missed / len(occurrences)

    if miss_ratio >= 0.6:
        return {
            "risk": "HIGH",
            "reason": "More than 60% missed recently"
        }

    if miss_ratio >= 0.3:
        return {
            "risk": "MEDIUM",
            "reason": "Inconsistent completion pattern"
        }

    return {
        "risk": "LOW",
        "reason": "Habit is stable"
    }
