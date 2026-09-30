from typing import Literal

from pydantic import (
    BaseModel,
    Field,
    field_validator,
)


Goal = Literal[
    "weight loss",
    "muscle gain",
    "general wellness",
    "flexibility",
    "fitness",
]


Intensity = Literal[
    "low",
    "medium",
    "high",
]


class UserInput(BaseModel):
    """
    Input information supplied by a FitBuddy user.
    """

    user_id: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    name: str = Field(
        min_length=2,
        max_length=120,
    )

    age: int = Field(
        ge=13,
        le=100,
    )

    weight: float = Field(
        gt=20,
        le=500,
    )

    goal: Goal

    intensity: Intensity

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:

        value = " ".join(
            value.split()
        )

        if not value:
            raise ValueError(
                "Name cannot be empty"
            )

        return value


class FeedbackRequest(BaseModel):
    """
    User feedback used to regenerate a plan.
    """

    user_id: str = Field(
        min_length=2,
        max_length=80,
        pattern=r"^[A-Za-z0-9_-]+$",
    )

    feedback: str = Field(
        min_length=5,
        max_length=1200,
    )

    @field_validator("feedback")
    @classmethod
    def clean_feedback(cls, value: str) -> str:

        value = " ".join(
            value.split()
        )

        if not value:
            raise ValueError(
                "Feedback cannot be empty"
            )

        return value


class Exercise(BaseModel):
    """
    Individual exercise.
    """

    name: str

    sets: str

    reps_or_duration: str

    rest: str


class WorkoutDay(BaseModel):
    """
    One day of the seven-day workout plan.
    """

    day: str

    focus: str

    warmup: str

    exercises: list[Exercise]

    cooldown: str

    @field_validator("exercises")
    @classmethod
    def validate_exercises(cls, value: list[Exercise]) -> list[Exercise]:
        if not (1 <= len(value) <= 8):
            raise ValueError("Exercises count must be between 1 and 8")
        return value


class WorkoutPlan(BaseModel):
    """
    Complete seven-day plan.
    """

    days: list[WorkoutDay]

    general_note: str

    @field_validator("days")
    @classmethod
    def validate_days(cls, value: list[WorkoutDay]) -> list[WorkoutDay]:
        if len(value) != 7:
            raise ValueError("Workout plan must contain exactly 7 days")
        return value


class PlanResponse(BaseModel):
    """
    API response for plan generation.
    """

    user_id: str

    name: str

    age: int

    weight: float

    goal: str

    intensity: str

    workout_plan: WorkoutPlan

    nutrition_tip: str

    plan_id: int