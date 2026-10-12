from collections.abc import Iterator

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session, sessionmaker

from app.config import settings

db_engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False)


def prepare_database() -> None:
    from app.models import Base

    Base.metadata.create_all(bind=db_engine)
    columns = {column["name"] for column in inspect(db_engine).get_columns("analyses")}
    if "mate_line" not in columns:
        with db_engine.begin() as connection:
            connection.execute(text("ALTER TABLE analyses ADD COLUMN mate_line JSON"))


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
