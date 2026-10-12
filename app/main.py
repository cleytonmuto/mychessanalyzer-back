import io
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import chess
import chess.pgn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db, prepare_database
from app.engine import position_error, stockfish
from app.models import Analysis, SavedGame, SavedPosition
from app.schemas import AnalysisRead, AnalyzeRequest, GameCreate, GameRead, PlayReply, PlayRequest, PositionCreate, PositionRead


@asynccontextmanager
async def lifespan(_app: FastAPI):
    prepare_database()
    stockfish.start()
    yield
    stockfish.stop()


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


def read_board(fen: str) -> chess.Board:
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="This position is not a valid chess position.") from exc
    error = position_error(board)
    if error:
        raise HTTPException(status_code=422, detail=error)
    return board


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/analyses", response_model=list[AnalysisRead])
def list_analyses(db: Session = Depends(get_db)) -> list[Analysis]:
    return list(db.scalars(select(Analysis).order_by(Analysis.created_at.desc()).limit(8)))


@app.post("/api/analyses", response_model=AnalysisRead)
def create_analysis(payload: AnalyzeRequest, db: Session = Depends(get_db)) -> Analysis:
    fen = payload.fen.strip()
    board = read_board(fen)
    try:
        result = stockfish.analyze(board)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Stockfish was not found. Check STOCKFISH_PATH.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Stockfish could not analyze this position.") from exc

    row = Analysis(
        fen=fen,
        best_move_uci=result.best_move_uci,
        best_move_san=result.best_move_san,
        from_square=result.from_square,
        to_square=result.to_square,
        score_type=result.score_type,
        score_value=result.score_value,
        evaluation_label=result.evaluation_label,
        depth=result.depth,
        mate_line=result.mate_line,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def board_for_play(fen: str, sans: list[str]) -> chess.Board:
    if not sans:
        return read_board(fen)
    board = chess.Board()
    try:
        for san in sans:
            board.push_san(san)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="This game contains a move that is not legal.") from exc
    error = position_error(board)
    if error:
        raise HTTPException(status_code=422, detail=error)
    return board


@app.post("/api/play", response_model=PlayReply)
def play_move(payload: PlayRequest) -> PlayReply:
    board = board_for_play(payload.fen.strip(), [san.strip() for san in payload.sans if san.strip()])
    if board.is_game_over():
        raise HTTPException(status_code=422, detail="The game is already over.")
    try:
        result = stockfish.reply(board, payload.depth)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="Stockfish was not found. Check STOCKFISH_PATH.") from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Stockfish could not play a move.") from exc
    if not result.best_move_uci or not result.best_move_san or not result.from_square or not result.to_square:
        raise HTTPException(status_code=503, detail="Stockfish did not return a move.")
    return PlayReply(
        uci=result.best_move_uci,
        san=result.best_move_san,
        from_square=result.from_square,
        to_square=result.to_square,
        evaluation_label=result.evaluation_label,
        score_type=result.score_type,
        score_value=result.score_value,
        depth=result.depth,
    )


def read_pgn(pgn: str) -> chess.pgn.Game:
    game = chess.pgn.read_game(io.StringIO(pgn))
    if game is None:
        raise HTTPException(status_code=422, detail="This is not a valid PGN game.")
    board = game.board()
    try:
        for move in game.mainline_moves():
            board.push(move)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="This PGN contains a move that is not legal.") from exc
    return game


def read_fen(fen: str) -> str:
    try:
        board = chess.Board(fen)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="This is not a valid FEN.") from exc
    return board.fen()


@app.get("/api/positions", response_model=list[PositionRead])
def list_positions(db: Session = Depends(get_db)) -> list[SavedPosition]:
    return list(db.scalars(select(SavedPosition).order_by(SavedPosition.created_at.desc()).limit(12)))


@app.post("/api/positions", response_model=PositionRead)
def create_position(payload: PositionCreate, db: Session = Depends(get_db)) -> SavedPosition:
    row = SavedPosition(fen=read_fen(payload.fen.strip()), created_at=datetime.now(timezone.utc))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@app.get("/api/games", response_model=list[GameRead])
def list_games(db: Session = Depends(get_db)) -> list[SavedGame]:
    return list(db.scalars(select(SavedGame).order_by(SavedGame.created_at.desc()).limit(12)))


@app.post("/api/games", response_model=GameRead)
def create_game(payload: GameCreate, db: Session = Depends(get_db)) -> SavedGame:
    game = read_pgn(payload.pgn.strip())
    headers = game.headers
    row = SavedGame(
        pgn=str(game),
        white=headers.get("White", "White") or "White",
        black=headers.get("Black", "Black") or "Black",
        result=headers.get("Result", "*") or "*",
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
