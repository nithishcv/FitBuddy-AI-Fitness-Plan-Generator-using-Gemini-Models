from app.schemas import UserInput, WorkoutDay, WorkoutPlan


def test_user_input_validation():
    user = UserInput(
        user_id="abc_01",
        name="Test User",
        age=25,
        weight=70,
        goal="muscle gain",
        intensity="medium",
    )

    assert user.user_id == "abc_01"
    assert user.name == "Test User"
    assert user.age == 25
    assert user.weight == 70
    assert user.goal == "muscle gain"
    assert user.intensity == "medium"


def test_workout_schema_requires_seven_days():
    day = WorkoutDay(
        day="Day 1",
        focus="General fitness",
        warmup="5 minutes",
        exercises=[
            {
                "name": "Walking",
                "sets": "1",
                "reps_or_duration": "20 minutes",
                "rest": "As needed",
            }
        ], # type: ignore
        cooldown="5 minutes easy movement",
    )

    plan = WorkoutPlan(days=[day] * 7, general_note="Progress gradually.")

    assert len(plan.days) == 7