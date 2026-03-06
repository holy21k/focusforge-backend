def generate_feedback(analysis: dict):
    if analysis["consistency"] > 0.85:
        return "You are consistent. Increase difficulty or add a second habit."

    if analysis["discipline_declining"]:
        return "Your discipline is slipping. Reduce target or adjust time window."

    if analysis["missed"] > analysis["completed"]:
        return "This habit is misaligned with your schedule. Redesign it."

    return "Maintain current habit. Monitor next 7 days."


def generate_ai_welcome_message():
    """Generate a welcoming message for first-time AI users."""
    return {
        "title": "👋 Welcome to Your AI Habit Coach!",
        "message": "I'm here to help you build lasting habits. I analyze your patterns and give personalized insights.",
        "features": [
            "📊 Predict your success probability",
            "⏰ Find your optimal completion time",
            "📅 Identify difficult days",
            "💡 Smart suggestions based on your data"
        ],
        "tip": "The more you log, the smarter my recommendations become!"
    }


def generate_smart_suggestions(habit_id: str, user_id: str, analysis: dict, predict_result: dict, optimal_time: dict, difficult_days: dict) -> dict:
    """Generate smart, actionable suggestions based on all available data."""
    suggestions = []
    
    # Analyze success prediction
    if predict_result.get("method") == "ml" and predict_result.get("probability", 0) < 0.5:
        suggestions.append({
            "type": "warning",
            "importance": "high",
            "title": "⚠️ Low Success Probability",
            "message": f"Based on your patterns, you have only {predict_result.get('probability', 0)*100:.0f}% chance of completing this habit. Consider adjusting your schedule.",
            "action": "Try the optimal time below or reduce difficulty temporarily."
        })
    
    # Analyze optimal time
    if optimal_time.get("optimal_hour") and optimal_time.get("completion_rate", 0) > 0:
        suggestions.append({
            "type": "insight",
            "importance": "medium",
            "title": "🕐 Optimal Time Detected",
            "message": f"You complete this habit best around {optimal_time['optimal_hour']}:00 ({optimal_time['completion_rate']*100:.0f}% completion rate).",
            "action": "Schedule this habit around that time for best results."
        })
    
    # Analyze difficult days
    if difficult_days.get("difficult_days"):
        difficult = [d["day"] for d in difficult_days["difficult_days"][:3]]
        suggestions.append({
            "type": "warning",
            "importance": "medium",
            "title": "📅 Challenge Days Ahead",
            "message": f"You struggle most on: {', '.join(difficult)}.",
            "action": "Consider lowering expectations on these days or preparing in advance."
        })
    
    # Analyze consistency
    if analysis.get("consistency", 0) < 0.5:
        suggestions.append({
            "type": "tip",
            "importance": "high",
            "title": "💡 Building Momentum",
            "message": "Your completion rate is below 50%. Let's fix that!",
            "action": "Try starting with a smaller commitment - just 5 minutes or 1 rep."
        })
    elif analysis.get("consistency", 0) > 0.8:
        suggestions.append({
            "type": "celebration",
            "importance": "low",
            "title": "🎉 Excellent Progress!",
            "message": f"You're maintaining {analysis['consistency']*100:.0f}% consistency! You're ready to level up.",
            "action": "Consider increasing difficulty or adding a related habit."
        })
    
    # Analyze streaks
    streak = analysis.get("current_streak", 0)
    if streak >= 7:
        suggestions.append({
            "type": "celebration",
            "importance": "low",
            "title": "🔥 {}-Day Streak!".format(streak),
            "message": "You're on fire! Keep this momentum going.",
            "action": "You're building a powerful habit. Don't break the chain!"
        })
    elif streak == 0 and analysis.get("total", 0) > 10:
        suggestions.append({
            "type": "warning",
            "importance": "high",
            "title": "🔄 Streak Reset",
            "message": "Your current streak is 0, but you have history. Let's rebuild!",
            "action": "Start fresh today - every day is a new opportunity."
        })
    
    # Sort by importance
    importance_order = {"high": 0, "medium": 1, "low": 2}
    suggestions.sort(key=lambda x: importance_order.get(x.get("importance", "low"), 2))
    
    return {
        "suggestions": suggestions,
        "summary": f"You have {len(suggestions)} insight{'s' if len(suggestions) != 1 else ''} to review."
    }
