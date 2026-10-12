from datetime import datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[int] = mapped_column(primary_key=True)
    fen: Mapped[str] = mapped_column(String(128), nullable=False)
    best_move_uci: Mapped[str | None] = mapped_column(String(8))
    best_move_san: Mapped[str | None] = mapped_column(String(16))
    from_square: Mapped[str | None] = mapped_column(String(2))
    to_square: Mapped[str | None] = mapped_column(String(2))
    score_type: Mapped[str] = mapped_column(String(16), nullable=False)
    score_value: Mapped[int | None] = mapped_column(Integer)
    evaluation_label: Mapped[str] = mapped_column(String(200), nullable=False)
    depth: Mapped[int] = mapped_column(Integer, nullable=False)
    mate_line: Mapped[list[dict[str, str]] | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SavedPosition(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    fen: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class SavedGame(Base):
    __tablename__ = "games"

    id: Mapped[int] = mapped_column(primary_key=True)
    pgn: Mapped[str] = mapped_column(Text, nullable=False)
    white: Mapped[str] = mapped_column(String(80), nullable=False)
    black: Mapped[str] = mapped_column(String(80), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
