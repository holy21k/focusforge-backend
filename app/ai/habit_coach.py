def generate_feedback(analysis: dict):
    if analysis["consistency"] > 0.85:
        return "You are consistent. Increase difficulty or add a second habit."

    if analysis["discipline_declining"]:
        return "Your discipline is slipping. Reduce target or adjust time window."

    if analysis["missed"] > analysis["completed"]:
        return "This habit is misaligned with your schedule. Redesign it."

    return "Maintain current habit. Monitor next 7 days."
