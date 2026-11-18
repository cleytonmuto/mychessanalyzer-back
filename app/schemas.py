from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    fen: str = Field(min_length=15, max_length=128)


class ReviewRequest(BaseModel):
    fen: str = Field(min_length=15, max_length=128)
    depth: int = Field(default=10, ge=1, le=16)


class ReviewReply(BaseModel):
    best_move_uci: str | None
    best_move_san: str | None
    score_type: str
    score_value: int | None
    depth: int


class RobotStateIn(BaseModel):
    side: Literal["w", "b"]
    from_top: bool
    fen: str = Field(min_length=15, max_length=128)
    sans: list[str] = Field(default_factory=list, max_length=512)
    your_turn: bool
    thinking: bool
    result: str | None = None
    review_only: bool = False
    notice: str = ""
    orientation: Literal["white", "black"]


class RobotSession(RobotStateIn):
    id: str


class RobotCommandCreate(BaseModel):
    kind: Literal["start", "move"]
    side: Literal["w", "b"] | None = None
    from_top: bool | None = None
    san: str | None = Field(default=None, max_length=16)


class RobotCommand(BaseModel):
    id: int
    kind: Literal["start", "move"]
    side: Literal["w", "b"] | None = None
    from_top: bool | None = None
    san: str | None = None


class RobotPushResult(BaseModel):
    commands: list[RobotCommand]


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
