import json
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Form,
    Header,
    HTTPException,
    Request,
    status,
)

from fastapi.responses import HTMLResponse

from fastapi.templating import (
    Jinja2Templates,
)

from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .gemini_flash_generator import (
    generate_nutrition_tip_with_flash,
)
from .gemini_generator import (
    generate_workout_gemini,
)
from .schemas import (
    FeedbackRequest,
    UserInput,
)
from .services import (
    get_all_users,
    get_latest_plan,
    get_user,
    save_plan,
    save_user,
    update_plan,
)
from .updated_plan import (
    update_workout_plan,
)


router = APIRouter()


templates = Jinja2Templates(
    directory="app/templates"
)


def _plan_text(plan) -> str:
    """
    Convert Pydantic workout plan to JSON text
    for database storage.
    """

    return json.dumps(
        plan.model_dump(),
        indent=2,
        ensure_ascii=False,
    )


def _require_admin(
    x_admin_key: str | None = None,
    admin_key: str | None = None,
    cookie_key: str | None = None,
) -> None:
    """
    Validate optional admin key from header, query param, or cookie.
    """

    configured_key = (
        get_settings().admin_key
    )

    # If no key is configured, allow local/demo access.
    if not configured_key:
        return

    provided_key = x_admin_key or admin_key or cookie_key

    if provided_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin key.",
        )


# ============================================================
# HOME PAGE
# ============================================================

@router.get(
    "/",
    response_class=HTMLResponse,
)
def home(request: Request):

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "request": request,
        },
    )


# ============================================================
# HEALTH
# ============================================================

@router.get("/health")
def health():

    settings = get_settings()

    return {
        "status": "ok",
        "gemini_configured": bool(
            settings.gemini_api_key
        ),
        "workout_model": settings.workout_model,
        "nutrition_model": settings.nutrition_model,
    }


@router.get("/api/health")
def api_health():

    return health()


# ============================================================
# WEB: GENERATE WORKOUT
# ============================================================

@router.post(
    "/generate-workout",
    response_class=HTMLResponse,
)
def generate_workout_form(
    request: Request,

    user_id: Annotated[
        str,
        Form(),
    ],

    name: Annotated[
        str,
        Form(),
    ],

    age: Annotated[
        int,
        Form(),
    ],

    weight: Annotated[
        float,
        Form(),
    ],

    goal: Annotated[
        str,
        Form(),
    ],

    intensity: Annotated[
        str,
        Form(),
    ],

    db: Session = Depends(get_db),
):

    try:

        # Validate input
        data = UserInput(
            user_id=user_id,
            name=name,
            age=age,
            weight=weight,
            goal=goal,
            intensity=intensity,
        )

        # Generate workout
        workout = generate_workout_gemini(
            data
        )

        # Generate nutrition tip
        nutrition = (
            generate_nutrition_tip_with_flash(
                data
            )
        )

        # Save only after both Gemini requests succeed.
        user = save_user(
            db,
            data,
        )

        # Save plan
        plan = save_plan(
            db,
            user,
            _plan_text(workout),
            nutrition,
        )

        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={
                "request": request,
                "user": user,
                "plan": workout,
                "nutrition_tip": nutrition,
                "plan_id": plan.id,
                "message": None,
            },
        )

    except RuntimeError as exc:

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": str(exc),
            },
            status_code=503,
        )

    except Exception as exc:

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": str(exc),
            },
            status_code=500,
        )


# ============================================================
# WEB: SUBMIT FEEDBACK
# ============================================================

@router.post(
    "/submit-feedback",
    response_class=HTMLResponse,
)
def submit_feedback_form(
    request: Request,

    user_id: Annotated[
        str,
        Form(),
    ],

    feedback: Annotated[
        str,
        Form(),
    ],

    db: Session = Depends(get_db),
):

    try:

        data = FeedbackRequest(
            user_id=user_id,
            feedback=feedback,
        )

        user = get_user(
            db,
            data.user_id,
        )

        if not user:
            raise HTTPException(
                status_code=404,
                detail="User ID not found.",
            )

        plan = get_latest_plan(
            db,
            user,
        )

        if not plan:
            raise HTTPException(
                status_code=404,
                detail="No workout plan found for this user.",
            )

        # Use the latest revision as the source.
        source_plan = (
            plan.updated_plan
            or plan.original_plan
        )

        revised = update_workout_plan(
            source_plan,
            data.feedback,
            user.age,
            user.goal,
            user.intensity,
        )

        update_plan(
            db,
            plan,
            _plan_text(revised),
            data.feedback,
        )

        return templates.TemplateResponse(
            request=request,
            name="result.html",
            context={
                "request": request,
                "user": user,
                "plan": revised,
                "nutrition_tip": plan.nutrition_tip,
                "plan_id": plan.id,
                "message": (
                    "Your plan was updated "
                    "using your feedback."
                ),
            },
        )

    except HTTPException as exc:

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": exc.detail,
            },
            status_code=exc.status_code,
        )

    except Exception as exc:

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": str(exc),
            },
            status_code=500,
        )


# ============================================================
# WEB: ADMIN DASHBOARD
# ============================================================

@router.get(
    "/view-all-users",
    response_class=HTMLResponse,
)
def view_all_users(
    request: Request,

    x_admin_key: str | None = Header(
        default=None
    ),

    admin_key: str | None = None,

    db: Session = Depends(get_db),
):

    try:

        cookie_key = request.cookies.get("admin_key")

        _require_admin(
            x_admin_key,
            admin_key,
            cookie_key,
        )

        users = get_all_users(
            db
        )

        resp = templates.TemplateResponse(
            request=request,
            name="all_users.html",
            context={
                "request": request,
                "users": users,
            },
        )

        valid_key = get_settings().admin_key
        if admin_key and valid_key and admin_key == valid_key:
            resp.set_cookie("admin_key", admin_key, httponly=True)

        return resp

    except HTTPException as exc:

        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={
                "request": request,
                "message": exc.detail,
            },
            status_code=exc.status_code,
        )


# ============================================================
# API: GENERATE WORKOUT
# ============================================================

@router.post("/api/workouts")
def api_generate(
    data: UserInput,
    db: Session = Depends(get_db),
):

    try:

        user = save_user(
            db,
            data,
        )

        workout = generate_workout_gemini(
            data
        )

        nutrition = (
            generate_nutrition_tip_with_flash(
                data
            )
        )

        plan = save_plan(
            db,
            user,
            _plan_text(workout),
            nutrition,
        )

        return {
            "user_id": user.user_id,
            "plan_id": plan.id,
            "workout_plan": workout.model_dump(),
            "nutrition_tip": nutrition,
        }

    except RuntimeError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=f"AI generation failed: {exc}",
        ) from exc


# ============================================================
# API: UPDATE WORKOUT FROM FEEDBACK
# ============================================================

@router.post(
    "/api/workouts/{user_id}/feedback"
)
def api_feedback(
    user_id: str,

    payload: FeedbackRequest,

    db: Session = Depends(get_db),
):

    if payload.user_id != user_id:

        raise HTTPException(
            status_code=400,
            detail=(
                "Path user_id and payload "
                "user_id must match."
            ),
        )

    user = get_user(
        db,
        user_id,
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User ID not found.",
        )

    plan = get_latest_plan(
        db,
        user,
    )

    if not plan:

        raise HTTPException(
            status_code=404,
            detail="No workout plan found for this user.",
        )

    source_plan = (
        plan.updated_plan
        or plan.original_plan
    )

    try:

        revised = update_workout_plan(
            source_plan,
            payload.feedback,
            user.age,
            user.goal,
            user.intensity,
        )

        update_plan(
            db,
            plan,
            _plan_text(revised),
            payload.feedback,
        )

        return {
            "user_id": user.user_id,
            "plan_id": plan.id,
            "workout_plan": revised.model_dump(),
            "nutrition_tip": plan.nutrition_tip,
        }

    except RuntimeError as exc:

        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    except Exception as exc:

        raise HTTPException(
            status_code=502,
            detail=f"AI update failed: {exc}",
        ) from exc


# ============================================================
# API: ALL USERS
# ============================================================

@router.get("/api/users")
def api_users(
    x_admin_key: str | None = Header(
        default=None
    ),

    admin_key: str | None = None,

    db: Session = Depends(get_db),
):

    _require_admin(
        x_admin_key,
        admin_key,
    )

    users = get_all_users(
        db
    )

    result = []

    for user in users:

        plans = []

        for plan in user.plans:

            plans.append(
                {
                    "id": plan.id,

                    "original_plan": json.loads(
                        plan.original_plan
                    ),

                    "updated_plan": (
                        json.loads(
                            plan.updated_plan
                        )
                        if plan.updated_plan
                        else None
                    ),

                    "last_feedback": (
                        plan.last_feedback
                    ),

                    "nutrition_tip": (
                        plan.nutrition_tip
                    ),
                }
            )

        result.append(
            {
                "user_id": user.user_id,
                "name": user.name,
                "age": user.age,
                "weight": user.weight,
                "goal": user.goal,
                "intensity": user.intensity,
                "plans": plans,
            }
        )

    return result