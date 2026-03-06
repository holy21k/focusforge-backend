"""
AI Discipline Coach Routes for FocusForge
Provides real predictions, failure risk analysis, and discipline guidance
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.prediction_service import (
    analyze_user_behavior,
    predict_success_probability,
    get_personalized_insights,
    generate_discipline_recommendation
)
from app.services.auth_service import verify_token
from app.ai.habit_analyzer import (
    analyze_task_completion_patterns,
    predict_task_completion,
    get_user_task_patterns
)
from datetime import datetime, timedelta, date
from typing import Optional

router = APIRouter(prefix="/ai", tags=["AI Discipline Coach"])

optional_security = HTTPBearer(auto_error=False)

def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_security)
):
    """Return user_id if authenticated, None if not."""
    if not credentials or not credentials.credentials:
        return None
    payload = verify_token(credentials.credentials)
    if not payload:
        return None
    return payload.get("sub")


@router.get("/coach/status")
async def get_coach_status(current_user: Optional[str] = Depends(get_optional_user)):
    """
    Get AI Coach status and summary for the user
    Works with or without authentication
    """
    if current_user:
        analysis = analyze_user_behavior(current_user)
        return {
            "status": "active",
            "coach_type": "Discipline Coach",
            "user_level": get_discipline_level(analysis["productivity_score"]),
            "summary": {
                "productivity_score": round(analysis["productivity_score"], 1),
                "trend": analysis["recent_trend"],
                "total_habits": analysis["total_habits"],
                "average_streak": round(analysis["average_streak"], 1)
            },
            "authenticated": True
        }
    else:
        # Return generic status for unauthenticated users
        return {
            "status": "active",
            "coach_type": "Discipline Coach",
            "user_level": "New User",
            "summary": {
                "productivity_score": 0,
                "trend": "stable",
                "total_habits": 0,
                "average_streak": 0
            },
            "authenticated": False,
            "message": "Log in to get personalized AI insights"
        }


@router.get("/coach/tomorrow")
async def predict_tomorrow(current_user: Optional[str] = Depends(get_optional_user)):
    """
    AI Coach prediction for tomorrow's discipline
    Works with or without authentication
    """
    if current_user:
        analysis = analyze_user_behavior(current_user)
        
        # Get predictions for each habit
        habits_predictions = []
        habits = []
        from app.database import get_database
        db = get_database()
        habits = list(db.habits.find({"user_id": current_user}))
        
        for habit in habits:
            pred = predict_success_probability(current_user, str(habit["_id"]))
            if "error" not in pred:
                habits_predictions.append({
                    "habit_id": str(habit["_id"]),
                    "habit_name": habit.get("name", "Unnamed"),
                    "success_probability": pred["probability"],
                    "prediction": pred["prediction"],
                    "risk_level": "high" if pred["probability"] < 40 else "medium" if pred["probability"] < 70 else "low",
                    "recommendation": get_tomorrow_recommendation(pred)
                })
        
        # Calculate tomorrow's overall prediction
        if habits_predictions:
            avg_probability = sum(h["success_probability"] for h in habits_predictions) / len(habits_predictions)
            high_risk = [h for h in habits_predictions if h["risk_level"] == "high"]
        else:
            avg_probability = 0
            high_risk = []
        
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        
        return {
            "date": tomorrow,
            "authenticated": True,
            "overall_prediction": {
                "success_probability": round(avg_probability, 1),
                "level": "challenging" if avg_probability < 40 else "uncertain" if avg_probability < 70 else "likely",
                "confidence": "high" if len(habits_predictions) >= 5 else "medium" if len(habits_predictions) >= 2 else "low"
            },
            "habits_prediction": habits_predictions,
            "alerts": [
                {
                    "type": "warning" if len(high_risk) > 0 else "info",
                    "message": f"{len(high_risk)} habit(s) at high risk of failure tomorrow",
                    "habits": [h["habit_name"] for h in high_risk]
                }
            ] if high_risk else [],
            "coach_message": get_tomorrow_coach_message(analysis, avg_probability, len(high_risk))
        }
    else:
        # Return generic prediction for unauthenticated users
        tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d")
        return {
            "date": tomorrow,
            "authenticated": False,
            "overall_prediction": {
                "success_probability": 50,
                "level": "uncertain",
                "confidence": "low"
            },
            "habits_prediction": [],
            "alerts": [],
            "coach_message": "Create an account and start tracking habits to get personalized predictions!"
        }


@router.get("/coach/failure-risk")
async def analyze_failure_risk(current_user: Optional[str] = Depends(get_optional_user)):
    """
    Deep analysis of failure risks and warning signs
    """
    if not current_user:
        return {
            "authenticated": False,
            "message": "Log in to get personalized failure risk analysis",
            "risk_level": "unknown",
            "factors": []
        }
    
    analysis = analyze_user_behavior(current_user)
    
    return {
        "authenticated": True,
        "risk_level": "high" if analysis["productivity_score"] < 40 else "medium" if analysis["productivity_score"] < 70 else "low",
        "productivity_score": round(analysis["productivity_score"], 1),
        "factors": [
            {
                "type": "declining_trend" if analysis["recent_trend"] == "declining" else "stable",
                "description": "Your completion rate has been declining" if analysis["recent_trend"] == "declining" else "Your completion rate has been stable"
            }
        ],
        "recommendations": analysis["recommendations"][:3] if analysis["recommendations"] else []
    }


@router.get("/coach/weekly-score")
async def get_weekly_discipline_score(current_user: Optional[str] = Depends(get_optional_user)):
    """
    Get weekly discipline score
    """
    if not current_user:
        return {
            "authenticated": False,
            "message": "Log in to see your weekly discipline score",
            "score": 0,
            "trend": "stable"
        }
    
    analysis = analyze_user_behavior(current_user)
    
    return {
        "authenticated": True,
        "score": round(analysis["productivity_score"], 1),
        "trend": analysis["recent_trend"],
        "details": {
            "total_habits": analysis["total_habits"],
            "average_streak": round(analysis["average_streak"], 1)
        }
    }


@router.get("/coach/recommendations")
async def get_discipline_recommendations(current_user: Optional[str] = Depends(get_optional_user)):
    """
    Get personalized discipline recommendations
    """
    if not current_user:
        return {
            "authenticated": False,
            "message": "Log in to get personalized recommendations",
            "recommendations": []
        }
    
    analysis = analyze_user_behavior(current_user)
    recommendations = generate_discipline_recommendation(analysis)
    
    return {
        "authenticated": True,
        "recommendations": recommendations
    }


@router.get("/coach/insights")
async def get_all_coach_insights(current_user: Optional[str] = Depends(get_optional_user)):
    """
    Get all coach insights in one call
    """
    status = await get_coach_status(current_user)
    tomorrow = await predict_tomorrow(current_user)
    failure_risk = await analyze_failure_risk(current_user)
    weekly_score = await get_weekly_discipline_score(current_user)
    
    return {
        "coach_status": status,
        "tomorrow_prediction": tomorrow,
        "failure_risk": failure_risk,
        "weekly_score": weekly_score,
        "generated_at": datetime.utcnow().isoformat()
    }


# Helper functions (keep from original)
def get_discipline_level(score):
    """Get user discipline level based on productivity score"""
    if score >= 80:
        return "Elite"
    elif score >= 60:
        return "Advanced"
    elif score >= 40:
        return "Intermediate"
    elif score >= 20:
        return "Beginner"
    else:
        return "Rebuilding"


def get_tomorrow_recommendation(prediction):
    """Get recommendation based on prediction"""
    prob = prediction.get("probability", 50)
    if prob >= 70:
        return "Great day to maintain momentum!"
    elif prob >= 40:
        return "Stay focused, you can do this!"
    else:
        return "Consider adjusting your approach tomorrow"


def get_tomorrow_coach_message(analysis, avg_probability, high_risk_count):
    """Generate coach message for tomorrow"""
    score = analysis.get("productivity_score", 50)
    trend = analysis.get("recent_trend", "stable")
    
    if score >= 70 and trend == "improving":
        return "You're on fire! Keep building on this momentum."
    elif score >= 60:
        return "Solid progress. Stay consistent."
    elif score >= 40:
        return "Room for improvement. Focus on your goals."
    elif high_risk_count > 0:
        return f"{high_risk_count} habits need attention. Don't give up!"
    else:
        return "Let's make tomorrow a great day!"


# ===============================
# TASK AI ANALYSIS ROUTES
# ===============================

@router.get("/coach/task-patterns")
async def get_task_patterns(
    days: int = 30,
    current_user: Optional[str] = Depends(get_optional_user)
):
    """
    Get AI analysis of task completion patterns.
    
    The AI learns from your task history to provide insights:
    - Which days you complete tasks most often
    - When you tend to miss tasks
    - Best time of day for task completion
    """
    if not current_user:
        return {
            "authenticated": False,
            "message": "Log in to get personalized task pattern analysis",
            "patterns": None
        }
    
    analysis = analyze_task_completion_patterns(current_user, days=days)
    
    return {
        "authenticated": True,
        "analysis_period_days": days,
        "patterns": analysis
    }


@router.get("/coach/task-prediction")
async def predict_task_completion_route(
    due_date: str,
    task_title: str = None,
    current_user: Optional[str] = Depends(get_optional_user)
):
    """
    Predict the likelihood of completing a task on a specific date.
    
    Args:
        due_date: ISO format date string (YYYY-MM-DD)
        task_title: Optional task title for context
    
    Returns:
        Prediction with probability and confidence level
    """
    if not current_user:
        return {
            "authenticated": False,
            "message": "Log in to get personalized task predictions"
        }
    
    try:
        target_date = datetime.fromisoformat(due_date).date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    prediction = predict_task_completion(current_user, target_date, task_title)
    
    return {
        "authenticated": True,
        "due_date": due_date,
        "task_title": task_title,
        "prediction": prediction
    }


@router.get("/coach/user-patterns")
async def get_all_user_patterns(
    current_user: Optional[str] = Depends(get_optional_user)
):
    """
    Get comprehensive task and habit patterns for the user.
    
    Used by the AI coach to provide personalized recommendations.
    """
    if not current_user:
        return {
            "authenticated": False,
            "message": "Log in to get personalized patterns"
        }
    
    patterns = get_user_task_patterns(current_user)
    
    return {
        "authenticated": True,
        "patterns": patterns,
        "generated_at": datetime.utcnow().isoformat()
    }
