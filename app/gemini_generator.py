import json
import re

from .config import get_settings, resolve_runtime_model
from .schemas import UserInput, WorkoutPlan


SYSTEM_INSTRUCTION = """
You are FitBuddy, a cautious wellness workout-planning assistant.

Create practical, age-appropriate fitness routines from the supplied profile.

Important safety requirements:

- Do not diagnose diseases.
- Do not prescribe medication.
- Do not recommend dangerous exercise practices.
- Do not encourage extreme dieting.
- Do not promise medical outcomes.
- Include appropriate rest and recovery.
- Keep exercise choices practical for a general wellness application.
- If the user is a minor, do not provide weight-loss dieting instructions.
- For minors, emphasize general fitness, enjoyable movement, balanced habits,
  hydration, sleep, and appropriate support from a parent/guardian or qualified
  professional when needed.

Return only the requested structured workout plan.
""".strip()


def _client():
    """
    Create the Gemini client lazily.

    Lazy importing prevents the whole application from crashing when
    the Google SDK is not installed during testing.
    """

    from google import genai

    settings = get_settings()

    if not settings.gemini_api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Copy .env.example to .env and add your Gemini API key."
        )

    return genai.Client(
        api_key=settings.gemini_api_key
    )


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


def _normalize_workout_json(raw_text: str) -> str:
    """Extract a valid WorkoutPlan JSON payload from noisy Gemini output."""

    text = (raw_text or "").strip()

    if not text:
        return text

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.IGNORECASE)
    text = text.strip()

    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = None

    def find_workout_payload(value):
        if isinstance(value, dict):
            if "days" in value and "general_note" in value:
                return value

            for key in ("profile", "plan", "result", "workout_plan", "workout"):
                nested = value.get(key)
                found = find_workout_payload(nested)
                if found is not None:
                    return found

            for nested in value.values():
                found = find_workout_payload(nested)
                if found is not None:
                    return found

        elif isinstance(value, list):
            for item in value:
                found = find_workout_payload(item)
                if found is not None:
                    return found

        return None

    if isinstance(payload, list):
        if payload and all(isinstance(item, dict) for item in payload):
            if all("day" in item for item in payload):
                return json.dumps({
                    "days": payload,
                    "general_note": "Progress gradually.",
                })

    workout_payload = find_workout_payload(payload)
    if workout_payload is not None:
        return json.dumps(workout_payload)

    if isinstance(payload, dict):
        for key in ("days", "plan"):
            nested = payload.get(key)
            if isinstance(nested, list) and nested and all(isinstance(item, dict) for item in nested):
                return json.dumps({
                    "days": nested,
                    "general_note": payload.get("general_note", "Progress gradually."),
                })

    return text


def generate_workout_gemini(
    user: UserInput,
) -> WorkoutPlan:
    """
    Generate a structured seven-day workout plan using Gemini.
    """

    from google.genai import types

    settings = get_settings()
    runtime_model = resolve_runtime_model(settings.workout_model)

    prompt = (
        "Create a personalized 7-day workout plan for:\n\n"
        f"Name:\n{user.name}\n\n"
        f"Age:\n{user.age}\n\n"
        f"Weight:\n{user.weight} kg\n\n"
        f"Goal:\n{user.goal}\n\n"
        f"Preferred intensity:\n{user.intensity}\n\n\n"
        "Requirements:\n\n"
        "1. Return ONLY valid JSON.\n\n"
        "2. The JSON must have exactly this top-level structure:\n"
        "   {\n"
        "     \"days\": [\n"
        "       {\n"
        "         \"day\": \"string\",\n"
        "         \"focus\": \"string\",\n"
        "         \"warmup\": \"string\",\n"
        "         \"exercises\": [\n"
        "           {\n"
        "             \"name\": \"string\",\n"
        "             \"sets\": \"string\",\n"
        "             \"reps_or_duration\": \"string\",\n"
        "             \"rest\": \"string\"\n"
        "           }\n"
        "         ],\n"
        "         \"cooldown\": \"string\"\n"
        "       }\n"
        "     ],\n"
        "     \"general_note\": \"string\"\n"
        "   }\n\n"
        "3. Return exactly 7 days.\n\n"
        "4. Each day must contain:\n"
        "   - day\n"
        "   - focus\n"
        "   - warmup\n"
        "   - exercises\n"
        "   - cooldown\n\n"
        "5. Each exercise must contain:\n"
        "   - name\n"
        "   - sets\n"
        "   - reps_or_duration\n"
        "   - rest\n\n"
        "6. Each day should contain between 1 and 8 exercises.\n\n"
        "7. Include suitable rest/recovery days where appropriate.\n\n"
        "8. Warm-up should generally be around 5–10 minutes.\n\n"
        "9. Make the plan practical and easy to understand.\n\n"
        "10. Do not prescribe calories.\n\n"
        "11. Do not prescribe supplements.\n\n"
        "12. Do not provide medication advice.\n\n"
        "13. Do not present this as medical treatment.\n\n"
        "14. If the user is under 18, avoid weight-loss dieting instructions.\n\n"
        "15. Do not include any extra keys such as name, age, goal, intensity, profile, or plan wrapper."
    )

    config_kwargs = {
        "system_instruction": SYSTEM_INSTRUCTION,
        "response_mime_type": "application/json",
        "temperature": 0.7,
        "max_output_tokens": 5000,
    }

    client = _client()
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
            # If succeeded, break out of model loop
            break
        except Exception as exc:
            last_exc = exc
            err_str = str(exc).lower()
            # If it's a quota, model not found, or temporary unavailability, try next fallback model
            if any(term in err_str for term in ["resource_exhausted", "quota", "rate limit", "429", "high demand", "unavailable", "503", "404", "not_found"]):
                continue
            # For other unexpected exceptions, re-raise immediately
            _raise_for_quota_or_rate_limit(exc)
            raise

    if response is None:
        if last_exc is not None:
            _raise_for_quota_or_rate_limit(last_exc)
            raise last_exc
        raise RuntimeError("Failed to generate workout plan.")

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
            "Gemini returned an empty workout plan."
        )

    normalized_text = _normalize_workout_json(response_text)

    return WorkoutPlan.model_validate_json(
        normalized_text
    )