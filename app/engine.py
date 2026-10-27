import threading
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine

from app.config import settings


@dataclass
class EngineResult:
    best_move_uci: str | None
    best_move_san: str | None
    from_square: str | None
    to_square: str | None
    score_type: str
    score_value: int | None
    evaluation_label: str
    depth: int
    mate_line: list[dict[str, str]] | None = None


_STATUS_MESSAGES: tuple[tuple[int, str], ...] = (
    (chess.STATUS_EMPTY, "The board is empty."),
    (chess.STATUS_NO_WHITE_KING, "White must have exactly one king."),
    (chess.STATUS_NO_BLACK_KING, "Black must have exactly one king."),
    (chess.STATUS_TOO_MANY_KINGS, "A position can have only one king per side."),
    (chess.STATUS_TOO_MANY_WHITE_PAWNS, "White has too many pawns."),
    (chess.STATUS_TOO_MANY_BLACK_PAWNS, "Black has too many pawns."),
    (chess.STATUS_PAWNS_ON_BACKRANK, "Pawns cannot stand on the first or eighth rank."),
    (chess.STATUS_TOO_MANY_WHITE_PIECES, "White has too many pieces."),
    (chess.STATUS_TOO_MANY_BLACK_PIECES, "Black has too many pieces."),
    (chess.STATUS_BAD_CASTLING_RIGHTS, "Castling rights do not match the king and rook positions."),
    (chess.STATUS_INVALID_EP_SQUARE, "The en passant square is not legal."),
    (
        chess.STATUS_OPPOSITE_CHECK,
        "The side waiting to move has its king in check. Switch the side to move, or move that king out of check.",
    ),
    (chess.STATUS_TOO_MANY_CHECKERS, "A king cannot be attacked by more than two pieces."),
    (chess.STATUS_IMPOSSIBLE_CHECK, "The check in this position cannot occur in a legal game."),
)


def position_error(board: chess.Board) -> str | None:
    status = board.status()
    if status == chess.STATUS_VALID:
        return None
    messages = [message for flag, message in _STATUS_MESSAGES if status & flag]
    return " ".join(messages) or "This position is not legal."


def _advantage_label(centipawns: int) -> str:
    if centipawns == 0:
        return "Neither side has an advantage."
    pawns = f"{abs(centipawns) / 100:.2f}"
    side = "White" if centipawns > 0 else "Black"
    return f"{side} is ahead by {pawns} pawns."


def _mate_label(mate: int) -> str:
    moves = abs(mate)
    noun = "move" if moves == 1 else "moves"
    side = "White" if mate > 0 else "Black"
    return f"Checkmate in {moves} {noun} for {side}."


def _terminal_result(board: chess.Board) -> EngineResult:
    outcome = board.outcome(claim_draw=True)
    empty = EngineResult(
        best_move_uci=None,
        best_move_san=None,
        from_square=None,
        to_square=None,
        score_type="draw",
        score_value=0,
        evaluation_label="The game is already drawn.",
        depth=0,
    )
    if board.is_checkmate() and outcome is not None:
        winner = "White" if outcome.winner == chess.WHITE else "Black"
        empty.score_type = "checkmate"
        empty.score_value = None
        empty.evaluation_label = f"{winner} has already delivered checkmate."
        return empty
    if board.is_stalemate():
        empty.score_type = "stalemate"
        empty.evaluation_label = "Stalemate. There is no legal move, and the king is not in check."
    return empty


def _move_dict(board: chess.Board, move: chess.Move) -> dict[str, str]:
    return {
        "san": board.san(move),
        "uci": move.uci(),
        "from_square": chess.square_name(move.from_square),
        "to_square": chess.square_name(move.to_square),
    }


def _mating_line(
    board: chess.Board,
    info: chess.engine.InfoDict,
    engine: chess.engine.SimpleEngine,
    depth: int,
) -> list[dict[str, str]] | None:
    white_score = info["score"].white()
    if not white_score.is_mate():
        return None
    mate = white_score.mate()
    if mate is None or abs(mate) < 2:
        return None

    scratch = board.copy(stack=False)
    line: list[dict[str, str]] = []

    def play(move: chess.Move) -> bool:
        line.append(_move_dict(scratch, move))
        scratch.push(move)
        return scratch.is_checkmate()

    for move in info.get("pv") or []:
        if play(move):
            return line

    guard = 0
    while not scratch.is_game_over() and guard < 30:
        guard += 1
        extra = engine.analyse(scratch, chess.engine.Limit(depth=depth))
        continuation = extra.get("pv") or []
        if not continuation:
            break
        if play(continuation[0]):
            return line
    return line or None


def _result_from_info(board: chess.Board, info: chess.engine.InfoDict, depth: int) -> EngineResult:
    pv = info.get("pv") or []
    if not pv:
        raise RuntimeError("Stockfish did not return a move.")
    move = pv[0]
    white_score = info["score"].white()
    reached_depth = int(info.get("depth") or depth)
    if white_score.is_mate():
        mate = white_score.mate()
        if mate is None:
            raise RuntimeError("Stockfish returned a mate score without a distance.")
        score_type = "mate"
        score_value = mate
        label = _mate_label(mate)
    else:
        centipawns = white_score.score()
        if centipawns is None:
            centipawns = 0
        score_type = "cp"
        score_value = centipawns
        label = _advantage_label(centipawns)
    return EngineResult(
        best_move_uci=move.uci(),
        best_move_san=board.san(move),
        from_square=chess.square_name(move.from_square),
        to_square=chess.square_name(move.to_square),
        score_type=score_type,
        score_value=score_value,
        evaluation_label=label,
        depth=reached_depth,
    )


def _move_draws(board: chess.Board, move: chess.Move) -> bool:
    board.push(move)
    try:
        return (
            board.is_stalemate()
            or board.is_insufficient_material()
            or board.is_repetition(3)
            or board.is_fifty_moves()
        )
    finally:
        board.pop()


class StockfishService:
    def __init__(self, path: str, depth: int) -> None:
        self.path = path
        self.depth = depth
        self._engine: chess.engine.SimpleEngine | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            self._close()
            if not Path(self.path).is_file():
                raise FileNotFoundError(self.path)
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)

    def stop(self) -> None:
        with self._lock:
            self._close()

    def analyze(self, board: chess.Board) -> EngineResult:
        if board.is_game_over(claim_draw=True):
            return _terminal_result(board)
        with self._lock:
            info = self._search(board, self.depth)[0]
            result = _result_from_info(board, info, self.depth)
            result.mate_line = _mating_line(board, info, self._require(), self.depth)
        return result

    def judge(self, board: chess.Board, depth: int) -> EngineResult:
        depth = max(1, min(depth, 16))
        with self._lock:
            info = self._search(board, depth)[0]
            return _result_from_info(board, info, depth)

    def reply(self, board: chess.Board, depth: int) -> EngineResult:
        if board.is_game_over():
            return _terminal_result(board)
        depth = max(1, min(depth, 16))
        with self._lock:
            info = self._choose_reply(board, depth)
            return _result_from_info(board, info, depth)

    def _choose_reply(self, board: chess.Board, depth: int) -> chess.engine.InfoDict:
        legal = list(board.legal_moves)
        excluded: list[chess.Move] = []
        fallback: chess.engine.InfoDict | None = None
        while True:
            root = [move for move in legal if move not in excluded]
            if not root:
                if fallback is None:
                    raise RuntimeError("Stockfish did not return a move.")
                return fallback
            infos = self._search(board, depth, multipv=min(5, len(root)), root_moves=root)
            progressed = False
            for info in infos:
                pv = info.get("pv") or []
                if not pv:
                    continue
                move = pv[0]
                if fallback is None:
                    fallback = info
                if move in excluded:
                    continue
                progressed = True
                if not _move_draws(board, move):
                    return info
                excluded.append(move)
            if not progressed:
                if fallback is None:
                    raise RuntimeError("Stockfish did not return a move.")
                return fallback

    def _search(
        self,
        board: chess.Board,
        depth: int,
        *,
        multipv: int = 1,
        root_moves: list[chess.Move] | None = None,
    ) -> list[chess.engine.InfoDict]:
        limit = chess.engine.Limit(depth=depth)
        options: dict[str, object] = {}
        if multipv > 1:
            options["multipv"] = multipv
        if root_moves is not None:
            options["root_moves"] = root_moves
        try:
            found = self._require().analyse(board, limit, **options)
        except (chess.engine.EngineTerminatedError, chess.engine.EngineError):
            self._close()
            self._engine = chess.engine.SimpleEngine.popen_uci(self.path)
            found = self._require().analyse(board, limit, **options)
        if isinstance(found, list):
            return found
        return [found]

    def _require(self) -> chess.engine.SimpleEngine:
        if self._engine is None:
            raise RuntimeError("Stockfish is not running.")
        return self._engine

    def _close(self) -> None:
        engine = self._engine
        self._engine = None
        if engine is None:
            return
        try:
            engine.quit()
        except chess.engine.EngineError:
            pass


stockfish = StockfishService(settings.stockfish_path, settings.engine_depth)
