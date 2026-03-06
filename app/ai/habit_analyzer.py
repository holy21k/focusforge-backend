from app.database import get_database
from datetime import date, timedelta, datetime
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
import pickle
import os
from bson import ObjectId


def analyze_habit(habit_id: str, user_id: str):
    """Traditional statistical analysis of habit performance."""
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


def get_streak_info(habit_id: str, user_id: str) -> dict:
    """Calculate current and longest streak for a habit."""
    db = get_database()
    
    occurrences = list(
        db.habit_occurrences.find(
            {"habit_id": habit_id, "user_id": user_id, "status": {"$in": ["completed", "missed"]}}
        ).sort("scheduled_date", -1)
    )
    
    if not occurrences:
        return {"current_streak": 0, "longest_streak": 0}
    
    current_streak = 0
    longest_streak = 0
    temp_streak = 0
    
    for occ in occurrences:
        if occ["status"] == "completed":
            temp_streak += 1
            if temp_streak > longest_streak:
                longest_streak = temp_streak
        else:
            temp_streak = 0
        
        # Current streak is only from completed occurrences at the start
        if current_streak == 0 and occ["status"] == "completed":
            current_streak = temp_streak
        elif current_streak == 0 and occ["status"] == "missed":
            current_streak = 0
    
    return {"current_streak": current_streak, "longest_streak": longest_streak}


def extract_features(occurrence: dict, streak_length: int, historical_rate: float) -> list:
    """Extract features from a habit occurrence.
    
    Features:
    - day_of_week (0-6, Monday-Sunday)
    - hour_of_day (0-23)
    - streak_length
    - historical_completion_rate
    - is_weekend (0 or 1)
    - day_of_month
    """
    scheduled_date = occurrence.get("scheduled_date")
    due_start = occurrence.get("due_start")
    
    if isinstance(scheduled_date, str):
        scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00')).date()
    elif hasattr(scheduled_date, 'date'):
        scheduled_date = scheduled_date.date()
    
    if isinstance(due_start, str):
        due_start = datetime.fromisoformat(due_start.replace('Z', '+00:00'))
    
    day_of_week = scheduled_date.weekday()  # 0 = Monday, 6 = Sunday
    
    if due_start:
        hour_of_day = due_start.hour
    else:
        hour_of_day = 12  # Default to noon if no due_start
    
    is_weekend = 1 if day_of_week >= 5 else 0
    day_of_month = scheduled_date.day
    
    return [
        day_of_week,
        hour_of_day,
        streak_length,
        historical_rate,
        is_weekend,
        day_of_month
    ]


def prepare_training_data(user_id: str = None, habit_id: str = None) -> tuple:
    """Prepare training data from habit occurrences.
    
    Returns:
    X: Feature matrix
    y: Target vector (1 = success/completed, 0 = failure/missed)
    """
    db = get_database()
    
    query = {"status": {"$in": ["completed", "missed"]}}
    if user_id:
        query["user_id"] = user_id
    if habit_id:
        query["habit_id"] = habit_id
    
    occurrences = list(db.habit_occurrences.find(query))
    
    if len(occurrences) < 10:
        return None, None
    
    X = []
    y = []
    
    for occ in occurrences:
        occ_habit_id = occ["habit_id"]
        
        # Get historical completion rate (excluding current occurrence)
        all_occurrences = list(
            db.habit_occurrences.find({
                "habit_id": occ_habit_id,
                "status": {"$in": ["completed", "missed"]},
                "_id": {"$ne": occ["_id"]}
            })
        )
        
        if not all_occurrences:
            historical_rate = 0.5
        else:
            completed_count = sum(1 for o in all_occurrences if o["status"] == "completed")
            historical_rate = completed_count / len(all_occurrences)
        
        # Get streak info
        streak_info = get_streak_info(occ_habit_id, occ["user_id"])
        
        features = extract_features(
            occ,
            streak_info["current_streak"],
            historical_rate
        )
        
        X.append(features)
        y.append(1 if occ["status"] == "completed" else 0)
    
    return np.array(X), np.array(y)


def train_classifier(user_id: str = None, habit_id: str = None) -> dict:
    """Train a Random Forest classifier on habit patterns.
    
    Returns:
    dict with model, scaler, accuracy, and feature importance
    """
    X, y = prepare_training_data(user_id, habit_id)
    
    if X is None or len(X) < 10:
        return {"error": "Insufficient data for training (minimum 10 occurrences required)"}
    
    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Train classifier
    clf = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=5,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    )
    clf.fit(X_train, y_train)
    
    # Evaluate
    train_score = clf.score(X_train, y_train)
    test_score = clf.score(X_test, y_test)
    
    # Feature importance
    feature_names = [
        "day_of_week",
        "hour_of_day",
        "streak_length",
        "historical_completion_rate",
        "is_weekend",
        "day_of_month"
    ]
    importance = dict(zip(feature_names, clf.feature_importances_.tolist()))
    
    return {
        "model": clf,
        "scaler": scaler,
        "train_accuracy": round(train_score, 4),
        "test_accuracy": round(test_score, 4),
        "feature_importance": importance,
        "samples_used": len(X)
    }


def predict_success(habit_id: str, user_id: str, scheduled_date: date = None) -> dict:
    """Predict the probability of successfully completing a habit.
    
    Args:
    habit_id: The habit ID
    user_id: The user ID
    scheduled_date: Optional date to predict for (defaults to today UTC)
    
    Returns:
    dict with prediction and probability
    """
    if scheduled_date is None:
        scheduled_date = datetime.utcnow().date()
    
    db = get_database()
    
    # Get habit info
    habit = db.habits.find_one({"_id": ObjectId(habit_id)})
    if not habit:
        return {"error": "Habit not found"}
    
    # Get streak info
    streak_info = get_streak_info(habit_id, user_id)
    
    # Get historical completion rate
    occurrences = list(
        db.habit_occurrences.find({
            "habit_id": habit_id,
            "status": {"$in": ["completed", "missed"]}
        })
    )
    
    if not occurrences:
        historical_rate = 0.5
    else:
        completed_count = sum(1 for o in occurrences if o["status"] == "completed")
        historical_rate = completed_count / len(occurrences)
    
    # Build occurrence-like dict for feature extraction
    due_start = datetime.combine(scheduled_date, habit.get("time_window_start", datetime.min.time()).time() if hasattr(habit.get("time_window_start"), "time") else datetime.min.time())
    
    occ = {
        "scheduled_date": scheduled_date,
        "due_start": due_start
    }
    
    features = extract_features(
        occ,
        streak_info["current_streak"],
        historical_rate
    )
    
    # Try to use trained model, otherwise use heuristic
    model_data = train_classifier(habit_id=habit_id)
    
    if "error" in model_data:
        # Fallback to heuristic prediction
        base_prob = historical_rate
        
        # Streak bonus/penalty
        streak_bonus = min(streak_info["current_streak"] * 0.02, 0.2)
        
        # Day of week effect (simplified)
        day_of_week = scheduled_date.weekday()
        if day_of_week >= 5:  # Weekend
            day_effect = -0.05
        else:
            day_effect = 0
        
        predicted_prob = min(max(base_prob + streak_bonus + day_effect, 0), 1)
        
        return {
            "predicted_success": predicted_prob > 0.5,
            "probability": round(predicted_prob, 4),
            "confidence": "low",
            "method": "heuristic",
            "reason": "Insufficient data for ML model"
        }
    
    # Use trained model
    X = np.array([features])
    X_scaled = model_data["scaler"].transform(X)
    
    proba = model_data["model"].predict_proba(X_scaled)[0]
    
    # Determine confidence based on test accuracy
    if model_data["test_accuracy"] >= 0.8:
        confidence = "high"
    elif model_data["test_accuracy"] >= 0.6:
        confidence = "medium"
    else:
        confidence = "low"
    
    return {
        "predicted_success": bool(model_data["model"].predict(X_scaled)[0]),
        "probability": round(proba[1], 4),
        "confidence": confidence,
        "method": "ml",
        "model_accuracy": model_data["test_accuracy"],
        "feature_importance": model_data["feature_importance"]
    }


def get_optimal_time(habit_id: str, user_id: str) -> dict:
    """Find the optimal time of day to complete a habit based on historical data."""
    db = get_database()
    
    occurrences = list(
        db.habit_occurrences.find({
            "habit_id": habit_id,
            "user_id": user_id,
            "status": "completed",
            "completed_at": {"$ne": None}
        })
    )
    
    if not occurrences:
        return {"optimal_hour": 12, "reason": "No completion data available"}
    
    # Analyze completion patterns by hour
    hour_completion = {}
    for occ in occurrences:
        completed_at = occ.get("completed_at")
        if completed_at:
            if isinstance(completed_at, str):
                completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            hour = completed_at.hour
            if hour not in hour_completion:
                hour_completion[hour] = {"completed": 0, "total": 0}
            hour_completion[hour]["completed"] += 1
            hour_completion[hour]["total"] += 1
    
    # Calculate completion rate by hour
    best_hour = None
    best_rate = -1
    for hour, data in hour_completion.items():
        rate = data["completed"] / data["total"]
        if rate > best_rate:
            best_rate = rate
            best_hour = hour
    
    return {
        "optimal_hour": best_hour,
        "completion_rate": round(best_rate, 2),
        "reason": f"Highest completion rate ({best_rate:.1%}) observed at {best_hour}:00"
    }


def get_difficult_days(habit_id: str, user_id: str) -> dict:
    """Identify days of the week that are most difficult for a habit."""
    db = get_database()
    
    occurrences = list(
        db.habit_occurrences.find({
            "habit_id": habit_id,
            "user_id": user_id,
            "status": {"$in": ["completed", "missed"]}
        })
    )
    
    if not occurrences:
        return {"difficult_days": [], "reason": "No occurrence data available"}
    
    day_stats = {i: {"completed": 0, "missed": 0} for i in range(7)}
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    for occ in occurrences:
        scheduled_date = occ.get("scheduled_date")
        if isinstance(scheduled_date, str):
            scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00')).date()
        
        day = scheduled_date.weekday()
        if occ["status"] == "completed":
            day_stats[day]["completed"] += 1
        else:
            day_stats[day]["missed"] += 1
    
    # Find days with lowest completion rate
    difficult_days = []
    for day, stats in day_stats.items():
        total = stats["completed"] + stats["missed"]
        if total > 0:
            rate = stats["completed"] / total
            if rate < 0.7:  # Less than 70% completion rate
                difficult_days.append({"day": day_names[day], "rate": rate})
    
    difficult_days.sort(key=lambda x: x["rate"])
    
    return {
        "difficult_days": difficult_days,
        "analysis": "Days with completion rate below 70%"
    }


# ===============================
# TASK COMPLETION PATTERNS (AI Learning)
# ===============================

def analyze_task_completion_patterns(user_id: str, days: int = 30) -> dict:
    """
    Analyze task completion patterns for AI learning.
    
    This helps the AI understand:
    - When the user tends to complete tasks
    - Which days tasks are most often missed
    - Task completion time patterns
    """
    db = get_database()
    
    # Get tasks from the last N days
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    
    tasks = list(db.tasks.find({
        "user_id": user_id,
        "created_at": {"$gte": cutoff_date}
    }))
    
    if not tasks:
        return {"error": "No task data available"}
    
    total = len(tasks)
    completed = sum(1 for t in tasks if t.get("is_completed"))
    missed = sum(1 for t in tasks if t.get("is_missed"))
    
    # Day of week analysis
    day_stats = {i: {"completed": 0, "missed": 0, "pending": 0} for i in range(7)}
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    
    # Completion time analysis
    completion_hours = []
    
    for task in tasks:
        due_date = task.get("due_date")
        if isinstance(due_date, str):
            due_date = datetime.fromisoformat(due_date.replace('Z', '+00:00')).date()
        elif hasattr(due_date, 'date'):
            due_date = due_date.date()
        
        day = due_date.weekday()
        
        if task.get("is_completed"):
            day_stats[day]["completed"] += 1
            
            # Track completion time
            completed_at = task.get("completed_at")
            if completed_at:
                if isinstance(completed_at, str):
                    completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
                completion_hours.append(completed_at.hour)
        elif task.get("is_missed"):
            day_stats[day]["missed"] += 1
        else:
            day_stats[day]["pending"] += 1
    
    # Calculate completion rate by day
    day_completion_rates = []
    for day, stats in day_stats.items():
        total_day = stats["completed"] + stats["missed"] + stats["pending"]
        if total_day > 0:
            rate = stats["completed"] / total_day
            day_completion_rates.append({
                "day": day_names[day],
                "completion_rate": round(rate, 2),
                "completed": stats["completed"],
                "missed": stats["missed"],
                "total": total_day
            })
    
    day_completion_rates.sort(key=lambda x: x["completion_rate"], reverse=True)
    
    # Best and worst days
    best_day = day_completion_rates[0] if day_completion_rates else None
    worst_day = day_completion_rates[-1] if day_completion_rates else None
    
    # Completion time pattern
    avg_completion_hour = None
    if completion_hours:
        avg_completion_hour = round(sum(completion_hours) / len(completion_hours))
    
    return {
        "total_tasks": total,
        "completed_tasks": completed,
        "missed_tasks": missed,
        "completion_rate": round(completed / total, 2) if total > 0 else 0,
        "day_analysis": day_completion_rates,
        "best_day": best_day,
        "worst_day": worst_day,
        "completion_time_pattern": {
            "average_hour": avg_completion_hour,
            "hours": completion_hours
        },
        "insights": generate_task_insights(day_completion_rates, missed, completed)
    }


def generate_task_insights(day_analysis: list, missed: int, completed: int) -> list:
    """Generate AI insights based on task completion patterns."""
    insights = []
    
    if missed > completed:
        insights.append("⚠️ You miss more tasks than you complete. Consider reducing your workload or setting more realistic goals.")
    
    # Check for pattern in worst days
    if day_analysis:
        best = day_analysis[0]
        worst = day_analysis[-1]
        if worst["completion_rate"] < 0.5:
            insights.append(f"📅 {worst['day']}s are challenging for you ({worst['completion_rate']:.0%} completion rate). Try scheduling important tasks on other days.")
        
        if best["completion_rate"] > 0.8:
            insights.append(f"✨ {best['day']}s are your most productive days! Schedule high-priority tasks on {best['day']}s.")
    
    return insights


def predict_task_completion(user_id: str, due_date: date, task_title: str = None) -> dict:
    """
    Predict the likelihood of completing a task on a specific date.
    
    Uses historical patterns to predict success probability.
    """
    analysis = analyze_task_completion_patterns(user_id, days=30)
    
    if "error" in analysis:
        return {
            "predicted_success": True,
            "probability": 0.5,
            "confidence": "low",
            "reason": "Insufficient historical data"
        }
    
    # Find completion rate for the specific day
    due_day_name = due_date.strftime("%A")
    day_rate = 0.5
    for day_info in analysis["day_analysis"]:
        if day_info["day"] == due_day_name:
            day_rate = day_info["completion_rate"]
            break
    
    # Base probability on historical pattern
    base_prob = day_rate
    
    # Adjust for streak (if any)
    recent_analysis = analyze_task_completion_patterns(user_id, days=7)
    if "error" not in recent_analysis:
        if recent_analysis["completion_rate"] > 0.7:
            base_prob += 0.1  # Boost for recent good performance
        elif recent_analysis["completion_rate"] < 0.3:
            base_prob -= 0.1  # Penalty for recent poor performance
    
    # Clamp probability
    predicted_prob = min(max(base_prob, 0), 1)
    
    # Determine confidence based on data quality
    confidence = "low"
    if analysis["total_tasks"] >= 20:
        confidence = "high"
    elif analysis["total_tasks"] >= 10:
        confidence = "medium"
    
    # Generate reason
    if predicted_prob >= 0.7:
        reason = f"Your completion rate on {due_day_name}s is {day_rate:.0%}"
    elif predicted_prob >= 0.4:
        reason = f"You complete about {day_rate:.0%} of tasks on {due_day_name}s"
    else:
        reason = f"You often miss tasks on {due_day_name}s ({day_rate:.0%} completion rate)"
    
    return {
        "predicted_success": predicted_prob > 0.5,
        "probability": round(predicted_prob, 2),
        "confidence": confidence,
        "reason": reason,
        "due_date": due_date.isoformat()
    }


def get_user_task_patterns(user_id: str) -> dict:
    """
    Get comprehensive task patterns for a user.
    
    This data is used by the AI coach to provide personalized recommendations.
    """
    short_term = analyze_task_completion_patterns(user_id, days=7)
    medium_term = analyze_task_completion_patterns(user_id, days=30)
    
    return {
        "short_term_patterns": short_term,
        "medium_term_patterns": medium_term,
        "prediction_model": "Available" if medium_term.get("total_tasks", 0) >= 10 else "Insufficient data"
    }
