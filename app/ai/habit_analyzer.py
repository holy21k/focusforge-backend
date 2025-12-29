from app.database import get_database
from datetime import date, timedelta


def analyze_habit(habit_id: str, user_id: str):
    db = get_database()

    occurrences = list(
        db.habit_occurrences.find(
            {"habit_id": habit_id, "user_id": user_id}
        ).sort("scheduled_date", -1)
    )

    if not occurrences:
        return None

    total = len(occurrences)
    completed = sum(1 for o in occurrences if o["status"] == "completed")
    missed = sum(1 for o in occurrences if o["status"] == "missed")

    consistency = completed / total

    recent = occurrences[:7]
    recent_completed = sum(1 for o in recent if o["status"] == "completed")

    decline = recent_completed < 3

    return {
        "total": total,
        "completed": completed,
        "missed": missed,
        "consistency": round(consistency, 2),
        "recent_performance": recent_completed,
        "discipline_declining": decline,
    }
