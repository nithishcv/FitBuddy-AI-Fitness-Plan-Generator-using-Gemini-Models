from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import User, WorkoutPlan
from .schemas import UserInput


def save_user(
    db: Session,
    data: UserInput,
) -> User:
    """
    Create a new user or update an existing user
    with the same user_id.
    """

    user = db.scalar(
        select(User).where(
            User.user_id == data.user_id
        )
    )

    if user is None:

        user = User(
            **data.model_dump()
        )

        db.add(user)

    else:

        values = data.model_dump()

        for key, value in values.items():
            setattr(
                user,
                key,
                value,
            )

    db.commit()

    db.refresh(user)

    return user


def save_plan(
    db: Session,
    user: User,
    original_plan: str,
    nutrition_tip: str,
) -> WorkoutPlan:
    """
    Save a newly generated workout plan.
    """

    plan = WorkoutPlan(
        user_id=user.id,
        original_plan=original_plan,
        nutrition_tip=nutrition_tip,
    )

    db.add(plan)

    db.commit()

    db.refresh(plan)

    return plan


def get_user(
    db: Session,
    user_id: str,
) -> User | None:
    """
    Find a user by public user_id.
    """

    return db.scalar(
        select(User).where(
            User.user_id == user_id
        )
    )


def get_latest_plan(
    db: Session,
    user: User,
) -> WorkoutPlan | None:
    """
    Get the latest plan belonging to a user.
    """

    return db.scalar(
        select(WorkoutPlan)
        .where(
            WorkoutPlan.user_id == user.id
        )
        .order_by(
            WorkoutPlan.id.desc()
        )
        .limit(1)
    )


def update_plan(
    db: Session,
    plan: WorkoutPlan,
    updated_plan: str,
    feedback: str,
    nutrition_tip: str | None = None,
) -> WorkoutPlan:
    """
    Store an AI-generated updated plan.
    """

    plan.updated_plan = updated_plan

    plan.last_feedback = feedback

    if nutrition_tip:
        plan.nutrition_tip = nutrition_tip

    db.commit()

    db.refresh(plan)

    return plan


def get_all_users(
    db: Session,
) -> list[User]:
    """
    Return all users ordered newest first.
    """

    return list(
        db.scalars(
            select(User).order_by(
                User.created_at.desc()
            )
        ).all()
    )