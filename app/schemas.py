from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    fen: str = Field(min_length=15, max_length=128)


class PlayRequest(BaseModel):
    fen: str = Field(min_length=15, max_length=128)
    depth: int = Field(default=10, ge=1, le=16)
    sans: list[str] = Field(default_factory=list, max_length=512)


class PositionCreate(BaseModel):
    fen: str = Field(min_length=15, max_length=128)


class PositionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fen: str
    created_at: datetime


class GameCreate(BaseModel):
    pgn: str = Field(min_length=8, max_length=20000)


class GameRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pgn: str
    white: str
    black: str
    result: str
    created_at: datetime


class PlayReply(BaseModel):
    uci: str
    san: str
    from_square: str
    to_square: str
    evaluation_label: str
    score_type: str
    score_value: int | None
    depth: int


class MateMove(BaseModel):
    san: str
    uci: str
    from_square: str
    to_square: str


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    fen: str
    best_move_uci: str | None
    best_move_san: str | None
    from_square: str | None
    to_square: str | None
    score_type: str
    score_value: int | None
    evaluation_label: str
    depth: int
    mate_line: list[MateMove] | None = None
    created_at: datetime
