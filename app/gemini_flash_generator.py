from .config import get_settings, resolve_runtime_model
from .schemas import UserInput


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


def generate_nutrition_tip_with_flash(
    user: UserInput,
) -> str:
    """
    Generate one concise nutrition/recovery tip.
    """

    from google import genai
    from google.genai import types

    settings = get_settings()
    runtime_model = resolve_runtime_model(settings.nutrition_model)

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Copy .env.example to .env and add your Gemini API key."
        )

    prompt = f"""
Give one concise nutrition or recovery tip for a FitBuddy user.

Goal:
{user.goal}

Age:
{user.age}

Workout intensity:
{user.intensity}

Requirements:

- Keep it practical.
- Keep it suitable for a general wellness application.
- Do not diagnose medical conditions.
- Do not prescribe medication.
- Do not prescribe supplements.
- Do not provide extreme dieting instructions.
- Do not provide calorie targets.
- If the user is under 18, avoid weight-loss dieting advice.
- Focus on balanced meals, hydration, sleep, and recovery.

Return one short paragraph only.
""".strip()

    client = genai.Client(
        api_key=settings.gemini_api_key
    )

    models_to_try = [runtime_model]
    for fallback in ["gemini-3.5-flash-lite", "gemini-3.8-flash"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_exc = None
    response = None

    for candidate_model in models_to_try:
        try:
            response = client.models.generate_content(
                model=candidate_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.5,
                    max_output_tokens=300,
                ),
            )
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
        raise RuntimeError("Failed to generate nutrition tip.")

    text = (
        response.text or ""
    ).strip()

    if not text:
        raise RuntimeError(
            "Gemini returned an empty nutrition tip."
        )

    return text