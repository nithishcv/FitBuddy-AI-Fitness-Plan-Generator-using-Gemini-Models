from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .database import init_db
from .routes import router


@asynccontextmanager
async def lifespan(
    app: FastAPI,
):
    """
    Application startup/shutdown lifecycle.
    """

    # Create database tables.
    init_db()

    yield


app = FastAPI(
    title="FitBuddy API",

    description=(
        "AI-powered 7-day fitness plan "
        "generator using Gemini."
    ),

    version="1.0.0",

    lifespan=lifespan,
)


@app.middleware("http")
async def no_cache_static_files(request, call_next):
    """Prevent stale browser caching for frontend assets in development."""
    response = await call_next(request)

    if request.url.path.startswith("/static/"):
        response.headers["Cache-Control"] = (
            "no-store, no-cache, must-revalidate, max-age=0"
        )
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

    return response


# Static CSS/JavaScript
app.mount(
    "/static",
    StaticFiles(
        directory="app/static"
    ),
    name="static",
)


# Application routes
app.include_router(
    router
)