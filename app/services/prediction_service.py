"""
AI Prediction and Analysis Service for FocusForge
Provides real predictions and suggestions based on user data
"""
from app.database import get_database
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def analyze_user_behavior(user_id: str) -> Dict:
    """
    Analyze user's habit and task behavior to generate insights
    """
    db = get_database()
    now = datetime.utcnow()
    
    # Get all habits
    habits = list(db.habits.find({"user_id": user_id}))
    tasks = list(db.tasks.find({"user_id": user_id}))
    
    analysis = {
        "total_habits": len(habits),
        "total_tasks": len(tasks),
        "completed_tasks": 0,
        "pending_tasks": 0,
        "habit_completion_rate": 0,
        "average_streak": 0,
        "best_habit": None,
        "struggling_habits": [],
        "productivity_score": 0,
        "peak_hours": [],
        "weak_days": [],
        "weekly_pattern": defaultdict(int),
        "recent_trend": "stable",  # improving, declining, stable
        "recommendations": []
    }
    
    # Analyze tasks
    for task in tasks:
        if task.get("is_completed", False):
            analysis["completed_tasks"] += 1
        else:
            analysis["pending_tasks"] += 1
    
    # Calculate completion rates
    if tasks:
        analysis["task_completion_rate"] = analysis["completed_tasks"] / len(tasks) * 100
    
    # Analyze habits
    if habits:
        total_completions = 0
        total_streaks = 0
        
        for habit in habits:
            occurrences = list(db.habit_occurrences.find({
                "habit_id": str(habit["_id"])
            }))
            
            completed = len([o for o in occurrences if o.get("status") == "completed"])
            total_completions += completed
            
            current_streak = habit.get("current_streak", 0)
            total_streaks += current_streak
            
            # Check if struggling (low completion)
            if occurrences:
                completion_rate = completed / len(occurrences)
                if completion_rate < 0.5:
                    analysis["struggling_habits"].append({
                        "name": habit.get("name", "Unnamed"),
                        "rate": completion_rate * 100
                    })
        
        analysis["habit_completion_rate"] = (
            total_completions / (len(habits) * 7) * 100 if habits else 0
        )
        analysis["average_streak"] = total_streaks / len(habits)
        
        # Find best habit
        best = max(habits, key=lambda h: h.get("consistency", 0))
        analysis["best_habit"] = {
            "name": best.get("name", "Unnamed"),
            "consistency": best.get("consistency", 0) * 100
        }
    
    # Calculate productivity score (0-100)
    task_rate = analysis["completed_tasks"] / max(1, len(tasks))
    habit_rate = analysis["habit_completion_rate"] / 100
    streak_bonus = min(analysis["average_streak"] * 2, 20)
    
    analysis["productivity_score"] = min(100, (
        task_rate * 30 + 
        habit_rate * 50 + 
        streak_bonus
    ))
    
    # Detect recent trend (last 7 days vs previous 7 days)
    week_ago = now - timedelta(days=7)
    recent_completions = sum(1 for t in tasks if t.get("is_completed") and 
                             t.get("completed_at", now) > week_ago)
    older_completions = sum(1 for t in tasks if t.get("is_completed") and 
                            t.get("completed_at", now) <= week_ago)
    
    if recent_completions > older_completions * 1.2:
        analysis["recent_trend"] = "improving"
    elif recent_completions < older_completions * 0.8:
        analysis["recent_trend"] = "declining"
    
    # Generate recommendations
    analysis["recommendations"] = generate_recommendations(analysis, habits)
    
    return analysis


def predict_success_probability(user_id: str, habit_id: str) -> Dict:
    """
    Predict probability of successfully completing a habit based on patterns
    """
    from bson import ObjectId
    db = get_database()
    
    # Convert habit_id to ObjectId if it's a string
    try:
        if isinstance(habit_id, str):
            habit_oid = ObjectId(habit_id)
        else:
            habit_oid = habit_id
    except:
        habit_oid = habit_id
    
    habit = db.habits.find_one({"_id": habit_oid, "user_id": user_id})
    if not habit:
        return {"error": "Habit not found"}
    
    # Get occurrence data - use scheduled_date field
    occurrences = list(db.habit_occurrences.find({
        "habit_id": habit_id
    }).sort("scheduled_date", -1).limit(14))  # Last 2 weeks
    
    # Calculate success rate
    completed = sum(1 for o in occurrences if o.get("status") == "completed")
    total = len(occurrences)
    base_rate = completed / max(1, total)
    
    # Analyze time patterns
    completion_hours = []
    for o in occurrences:
        if o.get("status") == "completed" and o.get("completed_at"):
            completed_at = o["completed_at"]
            if isinstance(completed_at, str):
                from datetime import datetime
                completed_at = datetime.fromisoformat(completed_at.replace('Z', '+00:00'))
            completion_hours.append(completed_at.hour)
    
    # Find best completion time
    if completion_hours:
        from collections import Counter
        hour_counts = Counter(completion_hours)
        best_hour = hour_counts.most_common(1)[0][0]
    else:
        best_hour = None
    
    # Analyze day patterns
    completion_days = []
    for o in occurrences:
        if o.get("status") == "completed" and o.get("scheduled_date"):
            scheduled_date = o["scheduled_date"]
            if isinstance(scheduled_date, str):
                from datetime import datetime
                scheduled_date = datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
            elif hasattr(scheduled_date, 'date'):
                # It's a datetime object, get the date
                scheduled_date = scheduled_date.date()
            completion_days.append(scheduled_date.weekday())
    
    difficult_days = []
    if completion_days:
        from collections import Counter
        day_counts = Counter(completion_days)
        all_days = set(range(7))
        completed_days = set(day_counts.keys())
        missing_days = all_days - completed_days
        
        for day in list(missing_days)[:3]:  # Top 3 difficult days
            day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            difficult_days.append(day_names[day])
    
    # Calculate prediction factors
    factors = {
        "consistency_score": base_rate * 100,
        "streak_momentum": min(habit.get("current_streak", 0) * 5, 25),
        "historical_pattern": base_rate * 30,
    }
    
    # Final probability
    probability = (
        base_rate * 0.5 +
        (habit.get("current_streak", 0) / 21) * 0.3 +
        (habit.get("longest_streak", 0) / 30) * 0.2
    )
    
    # Adjust for trend
    recent_occurrences = occurrences[:7]
    recent_rate = sum(1 for o in recent_occurrences if o.get("status") == "completed") / max(1, len(recent_occurrences))
    older_occurrences = occurrences[7:]
    older_rate = sum(1 for o in older_occurrences if o.get("status") == "completed") / max(1, len(older_occurrences))
    
    if recent_rate > older_rate * 1.2:
        probability = min(1, probability * 1.1)  # Boost for improving
    elif recent_rate < older_rate * 0.8:
        probability = max(0, probability * 0.9)  # Reduce for declining
    
    return {
        "habit_name": habit.get("name", "Unnamed"),
        "probability": round(probability * 100, 1),
        "confidence": "high" if total >= 10 else "medium" if total >= 5 else "low",
        "factors": factors,
        "optimal_hour": best_hour,
        "difficult_days": difficult_days,
        "total_completions": completed,
        "current_streak": habit.get("current_streak", 0),
        "prediction": "likely" if probability > 0.7 else "uncertain" if probability > 0.4 else "challenging"
    }


def generate_recommendations(analysis: Dict, habits: List) -> List[Dict]:
    """
    Generate actionable recommendations based on analysis
    """
    recommendations = []
    
    # Low productivity score
    if analysis["productivity_score"] < 40:
        recommendations.append({
            "type": "warning",
            "title": "🔄 Time to Rebuild",
            "message": "Your productivity score is low. Let's start fresh with one habit at a time.",
            "action": "Focus on your top priority habit for 7 days"
        })
    
    # Struggling habits
    if analysis["struggling_habits"]:
        for habit in analysis["struggling_habits"][:2]:  # Top 2
            recommendations.append({
                "type": "tip",
                "title": f"⚠️ {habit['name']} struggling",
                "message": f"This habit has only {habit['rate']:.0f}% completion rate.",
                "action": "Consider reducing frequency or changing the time"
            })
    
    # Improving trend
    if analysis["recent_trend"] == "improving":
        recommendations.append({
            "type": "celebration",
            "title": "📈 Great Momentum!",
            "message": "Your completion rate is improving. Keep it up!",
            "action": "Consider adding a new habit or increasing difficulty"
        })
    
    # Declining trend
    if analysis["recent_trend"] == "declining":
        recommendations.append({
            "type": "warning",
            "title": "📉 Focus Needed",
            "message": "Your completion rate has dropped recently.",
            "action": "Review your schedule and reduce commitments temporarily"
        })
    
    # Good progress
    if analysis["productivity_score"] > 70 and analysis["average_streak"] > 5:
        recommendations.append({
            "type": "celebration",
            "title": "🔥 You're on Fire!",
            "message": f"Productivity score: {analysis['productivity_score']:.0f}/100 with {analysis['average_streak']:.1f} day average streak!",
            "action": "You're ready to level up! Add a new challenge"
        })
    
    # No habits yet
    if analysis["total_habits"] == 0:
        recommendations.append({
            "type": "info",
            "title": "🚀 Start Your Journey",
            "message": "Create your first habit to begin building discipline!",
            "action": "Start with something small like 'Drink water' or '5 min stretch'"
        })
    
    return recommendations


def get_personalized_insights(user_id: str) -> Dict:
    """
    Get all personalized insights for the user
    """
    db = get_database()
    behavior = analyze_user_behavior(user_id)
    
    # Get predictions for each habit
    habits = list(db.habits.find({"user_id": user_id}))
    habit_predictions = []
    for habit in habits:
        pred = predict_success_probability(user_id, str(habit["_id"]))
        if "error" not in pred:
            habit_predictions.append(pred)
    
    return {
        "behavior_analysis": behavior,
        "habit_predictions": habit_predictions,
        "generated_at": datetime.utcnow().isoformat()
    }


def generate_discipline_recommendation(analysis: Dict) -> List[Dict]:
    """
    Generate discipline-focused recommendations for the AI Coach
    """
    recommendations = []
    
    # Critical: Low productivity score
    if analysis["productivity_score"] < 30:
        recommendations.append({
            "type": "critical",
            "priority": 1,
            "title": "🔄 Rebuild Your Foundation",
            "message": "Your productivity is at a low point. Let's simplify to just ONE habit for 7 days.",
            "action": "Choose your most important habit and focus exclusively on it",
            "expected_impact": "Recovery in 7-14 days"
        })
    
    # High: Declining trend
    elif analysis["recent_trend"] == "declining":
        recommendations.append({
            "type": "warning",
            "priority": 2,
            "title": "📉 Trend Alert",
            "message": "Your productivity has declined recently. Something in your routine isn't working.",
            "action": "Identify what's changed and simplify your commitments",
            "expected_impact": "Stabilization in 5-7 days"
        })
    
    # Medium: Struggling habits
    if analysis["struggling_habits"]:
        for i, habit in enumerate(analysis["struggling_habits"][:2]):
            recommendations.append({
                "type": "action",
                "priority": 3 + i,
                "title": f"🎯 Fix '{habit['name']}'",
                "message": f"This habit has only {habit['rate']:.0f}% completion. It's misaligned with your lifestyle.",
                "action": "Option 1: Reduce frequency | Option 2: Change time | Option 3: Make smaller",
                "expected_impact": "Recovery in 7-14 days with adjustment"
            })
    
    # Positive: Improving trend
    if analysis["recent_trend"] == "improving":
        recommendations.append({
            "type": "celebration",
            "priority": 10,
            "title": "📈 Great Momentum!",
            "message": "You're getting better! Your discipline is building.",
            "action": "Maintain current habits or add one small challenge",
            "expected_impact": "Continued improvement"
        })
    
    # Positive: High performance
    if analysis["productivity_score"] >= 70 and analysis["average_streak"] >= 5:
        recommendations.append({
            "type": "challenge",
            "priority": 11,
            "title": "🔥 You're Ready to Level Up",
            "message": f"{analysis['productivity_score']:.0f}/100 score with {analysis['average_streak']:.1f} day average streak!",
            "action": "Consider adding a new habit or increasing difficulty of existing ones",
            "expected_impact": "突破 - Breaking through to elite level"
        })
    
    # Info: No habits
    if analysis["total_habits"] == 0:
        recommendations.append({
            "type": "info",
            "priority": 1,
            "title": "🚀 Start Your Journey",
            "message": "Create your first habit to begin building discipline!",
            "action": "Start with something small like 'Drink water' or '5 min stretch'",
            "expected_impact": "First habit in 7 days"
        })
    
    # Sort by priority
    recommendations.sort(key=lambda x: x["priority"])
    
    return recommendations
