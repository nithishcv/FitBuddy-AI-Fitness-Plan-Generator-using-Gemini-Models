import json
import os


# Test environment only.
os.environ["GEMINI_API_KEY"] = "test-key"


from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


class FakePlan:

    def model_dump(self):

        return {

            "days": [

                {
                    "day": f"Day {i}",

                    "focus": "General fitness",

                    "warmup": "5 minutes",

                    "exercises": [

                        {
                            "name": "Walking",

                            "sets": "1",

                            "reps_or_duration": "20 minutes",

                            "rest": "As needed",
                        }

                    ],

                    "cooldown": (
                        "5 minutes easy movement"
                    ),
                }

                for i in range(1, 8)
            ],

            "general_note": (
                "Progress gradually."
            ),
        }


def fake_workout(_data):

    from app.schemas import WorkoutPlan

    return WorkoutPlan.model_validate(
        FakePlan().model_dump()
    )


def fake_nutrition(_data):

    return (
        "Stay hydrated and include balanced "
        "meals with protein and produce."
    )


def test_default_model_names_are_valid():

    settings = get_settings()

    assert settings.workout_model == "gemini-3.5-flash-lite"
    assert settings.nutrition_model == "gemini-3.5-flash-lite"


def test_settings_refresh_when_environment_changes(monkeypatch):

    from app import config

    monkeypatch.setenv("FITBUDDY_WORKOUT_MODEL", "gemini-3.8-flash")
    monkeypatch.setenv("FITBUDDY_NUTRITION_MODEL", "gemini-3.8-flash")

    first_settings = config.get_settings()
    assert first_settings.workout_model == "gemini-3.8-flash"
    assert first_settings.nutrition_model == "gemini-3.8-flash"

    monkeypatch.setenv("FITBUDDY_WORKOUT_MODEL", "gemini-3.5-flash-lite")
    monkeypatch.setenv("FITBUDDY_NUTRITION_MODEL", "gemini-3.5-flash-lite")

    refreshed_settings = config.get_settings()

    assert refreshed_settings.workout_model == "gemini-3.5-flash-lite"
    assert refreshed_settings.nutrition_model == "gemini-3.5-flash-lite"


def test_unsupported_future_model_names_fall_back_to_default(monkeypatch):

    monkeypatch.setenv(
        "FITBUDDY_WORKOUT_MODEL",
        "gemini-99-future-preview",
    )
    monkeypatch.setenv(
        "FITBUDDY_NUTRITION_MODEL",
        "gemini-99-future-preview",
    )

    from app import config

    settings = config.get_settings()

    assert settings.workout_model == "gemini-3.5-flash-lite"
    assert settings.nutrition_model == "gemini-3.5-flash-lite"


def test_quota_exhausted_error_message_is_helpful(monkeypatch):

    from app import gemini_generator

    class FakeError(Exception):
        pass

    def fake_fail(*args, **kwargs):
        raise FakeError("429 RESOURCE_EXHAUSTED")

    monkeypatch.setattr(
        gemini_generator,
        "_client",
        lambda: type(
            "Client",
            (),
            {"models": type("Models", (), {"generate_content": staticmethod(fake_fail)})()},
        )(),
    )

    user = type(
        "User",
        (),
        {"name": "Test User", "age": 25, "weight": 70, "goal": "general wellness", "intensity": "medium"},
    )()

    try:
        gemini_generator.generate_workout_gemini(user)
        assert False, "Expected quota error to be raised"
    except RuntimeError as exc:
        message = str(exc)
        assert "quota" in message.lower()
        assert "billing" in message.lower()


def test_high_demand_unavailable_error_message_is_helpful(monkeypatch):

    from app import gemini_generator

    class FakeError(Exception):
        pass

    def fake_fail(*args, **kwargs):
        raise FakeError(
            "503 UNAVAILABLE: This model is currently experiencing high demand. "
            "Spikes in demand are usually temporary. Please try again later."
        )

    monkeypatch.setattr(
        gemini_generator,
        "_client",
        lambda: type(
            "Client",
            (),
            {"models": type("Models", (), {"generate_content": staticmethod(fake_fail)})()},
        )(),
    )

    user = type(
        "User",
        (),
        {"name": "Test User", "age": 25, "weight": 70, "goal": "general wellness", "intensity": "medium"},
    )()

    try:
        gemini_generator.generate_workout_gemini(user)
        assert False, "Expected high-demand unavailable error to be raised"
    except RuntimeError as exc:
        message = str(exc)
        assert "high demand" in message.lower()
        assert "try again later" in message.lower()


def test_home():

    with TestClient(app) as client:

        response = client.get("/")

        assert response.status_code == 200

        assert "FitBuddy" in response.text


def test_health():

    with TestClient(app) as client:

        response = client.get(
            "/api/health"
        )

        assert response.status_code == 200

        data = response.json()

        assert data["status"] == "ok"


def test_generate_workout_form_returns_503_for_quota_error(monkeypatch):

    from app import routes

    def raise_quota_error(_data):
        raise RuntimeError(
            "Google Gemini API quota is exhausted for this project."
        )

    monkeypatch.setattr(
        routes,
        "generate_workout_gemini",
        raise_quota_error,
    )

    with TestClient(app) as client:
        response = client.post(
            "/generate-workout",
            data={
                "user_id": "quota_test_user",
                "name": "Quota Test",
                "age": 30,
                "weight": 70,
                "goal": "general wellness",
                "intensity": "medium",
            },
        )

    assert response.status_code == 503
    assert "quota is exhausted" in response.text


def test_api_generate(monkeypatch):

    from app import routes


    monkeypatch.setattr(
        routes,
        "generate_workout_gemini",
        fake_workout,
    )


    monkeypatch.setattr(
        routes,
        "generate_nutrition_tip_with_flash",
        fake_nutrition,
    )


    with TestClient(app) as client:

        response = client.post(
            "/api/workouts",

            json={
                "user_id": "test_user",

                "name": "Test User",

                "age": 25,

                "weight": 70,

                "goal": "general wellness",

                "intensity": "medium",
            },
        )


        assert response.status_code == 200


        data = response.json()


        assert data["user_id"] == (
            "test_user"
        )


        assert "plan_id" in data


        assert len(
            data["workout_plan"]["days"]
        ) == 7


def test_generate_workout_gemini_handles_wrapped_profile_json(monkeypatch):

    from app import gemini_generator
    from app.schemas import UserInput

    class FakeResponse:
        text = json.dumps({"profile": FakePlan().model_dump()})
        parsed = None

    class FakeModels:

        def generate_content(self, model, contents, config):
            return FakeResponse()

    class FakeClient:

        def __init__(self):
            self.models = FakeModels()

    monkeypatch.setattr(
        gemini_generator,
        "_client",
        lambda: FakeClient(),
    )

    user = UserInput(
        user_id="testuser",
        name="Test User",
        age=25,
        weight=70,
        goal="general wellness",
        intensity="medium",
    )

    result = gemini_generator.generate_workout_gemini(user)

    assert len(result.days) == 7
    assert result.general_note == "Progress gradually."


def test_generate_workout_gemini_handles_top_level_day_list(monkeypatch):

    from app import gemini_generator
    from app.schemas import UserInput

    class FakeResponse:
        text = json.dumps(FakePlan().model_dump()["days"])
        parsed = None

    class FakeModels:

        def generate_content(self, model, contents, config):
            return FakeResponse()

    class FakeClient:

        def __init__(self):
            self.models = FakeModels()

    monkeypatch.setattr(
        gemini_generator,
        "_client",
        lambda: FakeClient(),
    )

    user = UserInput(
        user_id="testuser",
        name="Test User",
        age=25,
        weight=70,
        goal="general wellness",
        intensity="medium",
    )

    result = gemini_generator.generate_workout_gemini(user)

    assert len(result.days) == 7
    assert result.days[0].day == "Day 1"


def test_generate_workout_gemini_falls_back_when_schema_is_rejected(monkeypatch):

    from app import gemini_generator
    from app.schemas import UserInput


    class FakeResponse:

        parsed = None

        text = (
            '{"days": [{' \
            '"day": "Day 1", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}, {' \
            '"day": "Day 2", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}, {' \
            '"day": "Day 3", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}, {' \
            '"day": "Day 4", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}, {' \
            '"day": "Day 5", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}, {' \
            '"day": "Day 6", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}, {' \
            '"day": "Day 7", ' \
            '"focus": "General fitness", ' \
            '"warmup": "5 minutes", ' \
            '"exercises": [{"name": "Walking", "sets": "1", "reps_or_duration": "20 minutes", "rest": "As needed"}], ' \
            '"cooldown": "5 minutes easy movement"}], ' \
            '"general_note": "Progress gradually."}'
        )


    class FakeModels:

        def __init__(self):
            self.calls = []

        def generate_content(self, model, contents, config):
            self.calls.append(
                getattr(config, "response_schema", None)
            )

            if getattr(config, "response_schema", None) is not None:
                raise RuntimeError(
                    "400 INVALID_ARGUMENT. {'error': {'status': 'INVALID_ARGUMENT'}}"
                )

            return FakeResponse()


    class FakeClient:

        def __init__(self):
            self.models = FakeModels()


    monkeypatch.setattr(
        gemini_generator,
        "_client",
        lambda: FakeClient(),
    )

    user = UserInput(
        user_id="testuser",
        name="Test User",
        age=25,
        weight=70,
        goal="general wellness",
        intensity="medium",
    )

    result = gemini_generator.generate_workout_gemini(user)

    assert len(result.days) == 7
    assert result.days[0].day == "Day 1"