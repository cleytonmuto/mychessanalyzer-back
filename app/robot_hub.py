import threading
import time
import uuid
from dataclasses import dataclass, field

from app.schemas import RobotCommand, RobotCommandCreate, RobotSession, RobotStateIn

STALE_SECONDS = 60


@dataclass
class _Session:
    id: str
    state: RobotStateIn
    seen: float
    commands: list[RobotCommand] = field(default_factory=list)
    next_command: int = 1


class RobotHub:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, _Session] = {}

    def _prune(self, now: float) -> None:
        stale = [sid for sid, row in self._sessions.items() if now - row.seen > STALE_SECONDS]
        for sid in stale:
            del self._sessions[sid]

    def open(self) -> RobotSession:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            session_id = uuid.uuid4().hex[:8]
            state = RobotStateIn(
                side="w",
                from_top=False,
                fen="rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1",
                your_turn=True,
                thinking=False,
                notice="Waiting for the robot.",
                orientation="white",
            )
            self._sessions[session_id] = _Session(id=session_id, state=state, seen=now)
            return self._public(self._sessions[session_id])

    def push(self, session_id: str, state: RobotStateIn) -> list[RobotCommand]:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            row = self._sessions.get(session_id)
            if row is None:
                row = _Session(id=session_id, state=state, seen=now)
                self._sessions[session_id] = row
                return []
            row.state = state
            row.seen = now
            commands = row.commands
            row.commands = []
            return commands

    def list_sessions(self) -> list[RobotSession]:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            return [self._public(row) for row in self._sessions.values()]

    def enqueue(self, session_id: str, payload: RobotCommandCreate) -> RobotCommand:
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            row = self._sessions.get(session_id)
            if row is None:
                raise KeyError(session_id)
            command = RobotCommand(id=row.next_command, kind=payload.kind, side=payload.side, from_top=payload.from_top, san=payload.san)
            row.next_command += 1
            row.commands.append(command)
            row.seen = now
            return command

    def close(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)

    def _public(self, row: _Session) -> RobotSession:
        return RobotSession(id=row.id, **row.state.model_dump())


robot_hub = RobotHub()
