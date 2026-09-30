from .config import get_settings, resolve_runtime_model
from .schemas import WorkoutPlan


def _raise_for_quota_or_rate_limit(exc: Exception) -> None:
    """Translate Gemini quota/rate-limit or temporary overload failures into clear app messages."""
    message = str(exc).lower()

    if (
        "high demand" in message
        or "service unavailable" in message
        or "unavailable" in message
        or "503" in message
    ):
        raise RuntimeError(
            "Google Gemini is experiencing high demand. "
            "This model is temporarily unavailable. Please wait a few moments and try again later."
        ) from exc

    if (
        "resource_exhausted" in message
        or "quota" in message
        or "rate limit" in message
        or "429" in message
    ):
        raise RuntimeError(
            "Google Gemini API quota is exhausted for this project. "
            "Wait for the reset window or enable billing in Google AI Studio for the API key being used."
        ) from exc


SYSTEM_INSTRUCTION = """
You revise a previously generated wellness workout plan using user feedback.

Preserve useful structure while applying reasonable requested changes.

Safety requirements:

- Do not provide medical diagnosis.
- Do not provide medication advice.
- Do not provide extreme dieting instructions.
- Do not recommend dangerous exercise.
- If feedback requests something unsafe, use a safer alternative.
- If the user is a minor, avoid weight-loss dieting instructions.
- Include appropriate rest and recovery.

Return only the requested structured workout plan.
""".strip()


def update_workout_plan(
    original_plan: str,
    feedback: str,
    age: int,
    goal: str,
    intensity: str,
) -> WorkoutPlan:
    """
    Regenerate a workout plan using the original plan and user feedback.
    """

    from google import genai
    from google.genai import types

    settings = get_settings()

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Copy .env.example to .env and add your Gemini API key."
        )

    prompt = f"""
Revise this FitBuddy 7-day workout plan.

User age:
{age}

Goal:
{goal}

Preferred intensity:
{intensity}


USER FEEDBACK:
{feedback}


ORIGINAL PLAN:
{original_plan}


Requirements:

1. Return exactly 7 days.

2. Keep these fields:
   - day
   - focus
   - warmup
   - exercises
   - cooldown

3. Every exercise must contain:
   - name
   - sets
   - reps_or_duration
   - rest

4. Apply the feedback where reasonable.

5. Keep the revised plan practical and safe.

6. Include rest/recovery where appropriate.

7. Do not add calorie targets.

8. Do not add medication advice.

9. Do not prescribe supplements.

10. If the user is under 18, do not introduce weight-loss dieting instructions.
""".strip()

    client = genai.Client(
        api_key=settings.gemini_api_key
    )

    config_kwargs = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "response_mime_type": "application/json",
        "temperature": 0.7,
        "max_output_tokens": 5000,
    }

    runtime_model = resolve_runtime_model(settings.workout_model)

    models_to_try = [runtime_model]
    for fallback in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_exc = None
    response = None

    for candidate_model in models_to_try:
        try:
            try:
                response = client.models.generate_content(
                    model=candidate_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        **config_kwargs,
                        response_schema=WorkoutPlan,
                    ),
                )
            except Exception as exc:
                if "INVALID_ARGUMENT" in str(exc):
                    response = client.models.generate_content(
                        model=candidate_model,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            **config_kwargs,
                        ),
                    )
                else:
                    raise
            break
        except Exception as exc:
            last_exc = exc
            err_str = str(exc).lower()
            if any(term in err_str for term in ["resource_exhausted", "quota", "rate limit", "429", "high demand", "unavailable", "503", "404", "not_found"]):
                continue
            _raise_for_quota_or_rate_limit(exc)
            raise

    if response is None:
        if last_exc is not None:
            _raise_for_quota_or_rate_limit(last_exc)
            raise last_exc
        raise RuntimeError("Failed to generate updated workout plan.")

    parsed = getattr(
        response,
        "parsed",
        None,
    )

    if parsed is not None:
        if isinstance(parsed, WorkoutPlan):
            return parsed
        if hasattr(parsed, "model_dump"):
            return WorkoutPlan.model_validate(parsed.model_dump())
        return WorkoutPlan.model_validate(
            parsed
        )

    response_text = (
        response.text or ""
    ).strip()

    if not response_text:
        raise RuntimeError(
            "Gemini returned an empty updated plan."
        )

    return WorkoutPlan.model_validate_json(
        response_text
    )