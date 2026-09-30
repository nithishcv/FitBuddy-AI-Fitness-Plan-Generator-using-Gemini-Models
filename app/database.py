from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import BASE_DIR, get_settings


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.
    """

    pass


settings = get_settings()


database_url = settings.database_url


# If SQLite uses a relative path such as:
# sqlite:///./fitbuddy.db
# make sure it is located inside the project root.
if database_url.startswith("sqlite:///./"):

    relative_path = database_url.removeprefix(
        "sqlite:///./"
    )

    absolute_path = (
        BASE_DIR / relative_path
    ).resolve()

    database_url = (
        "sqlite:///"
        + str(absolute_path).replace("\\", "/")
    )


connect_args = {}

if database_url.startswith("sqlite"):
    connect_args = {
        "check_same_thread": False
    }


engine = create_engine(
    database_url,
    connect_args=connect_args,
    future=True,
)


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


def init_db() -> None:
    """
    Create all database tables.
    """

    # Import models so SQLAlchemy knows about them.
    from . import models  # noqa: F401

    Base.metadata.create_all(
        bind=engine
    )


def get_db():
    """
    FastAPI database dependency.
    """

    db = SessionLocal()

    try:
        yield db

    finally:
        db.close()