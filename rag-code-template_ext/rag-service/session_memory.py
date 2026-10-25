"""세션 단위 대화 보관 인터페이스와 단일 프로세스용 메모리 구현.

LLM·LangGraph·FastAPI와 독립적이다. 요약을 생성하지 않고 생성할 구간과
완성된 요약의 원자적 저장을 제공한다. 모든 공개 조회 결과는 불변 스냅샷이다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
import threading
from typing import Literal, Protocol, runtime_checkable
import uuid


CompletedStatus = Literal["answered", "clarification_needed", "no_evidence", "greeting", "out_of_scope"]
COMPLETED_STATUSES = {"answered", "clarification_needed", "no_evidence", "greeting", "out_of_scope"}


class SessionNotFoundError(LookupError):
    """알 수 없거나 종료·만료된 세션. 만료 세션은 복구하지 않는다."""


class SessionVersionConflict(RuntimeError):
    """읽은 스냅샷 뒤 다른 쓰기가 발생함. 다시 조회한 뒤 작업을 판단해야 한다."""


class RequestConflict(RuntimeError):
    """같은 세션의 같은 request_id로 서로 다른 완료 결과를 저장하려 함."""


class SessionCapacityError(RuntimeError):
    """활성 세션 한도. 아직 살아 있는 대화를 임의로 삭제하지 않는다."""


@dataclass(frozen=True)
class Turn:
    turn_id: int
    request_id: str
    question: str
    output: str
    status: CompletedStatus
    source_ids: tuple[str, ...]
    created_at: datetime


@dataclass(frozen=True)
class Summary:
    text: str = ""
    summarized_until_turn_id: int = 0
    updated_at: datetime | None = None


@dataclass(frozen=True)
class SessionSnapshot:
    session_id: str
    version: int
    turns: tuple[Turn, ...]
    summary: Summary
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime


@dataclass(frozen=True)
class SessionContext:
    """그래프 진입용. 전체 원문·요약 본문을 미리 전달하지 않는다."""
    session_id: str
    version: int
    recent_turns: tuple[Turn, ...]
    summary_available: bool
    summarized_until_turn_id: int
    summary_target_until_turn_id: int
    summary_is_current: bool
    expires_at: datetime


@dataclass(frozen=True)
class SummaryWork:
    """이 version에서 previous_summary와 turns 전체를 합쳐 요약해야 한다."""
    session_id: str
    version: int
    previous_summary: Summary
    turns: tuple[Turn, ...]
    target_until_turn_id: int


@dataclass(frozen=True)
class AppendResult:
    session_id: str
    version: int
    turn: Turn
    duplicate: bool


@runtime_checkable
class SessionStore(Protocol):
    """Redis/DB 구현도 유지할 비동기 계약. 인증·LLM 요약은 호출 계층의 책임이다."""
    async def create_session(self) -> SessionSnapshot: ...
    async def get_session(self, session_id: str, *, touch: bool = True) -> SessionSnapshot: ...
    async def get_context(self, session_id: str, *, touch: bool = True) -> SessionContext: ...
    async def get_recent_turns(self, session_id: str) -> tuple[Turn, ...]: ...
    async def get_turn_by_request(self, session_id: str, request_id: str) -> Turn | None: ...
    async def append_turn(self, session_id: str, *, expected_version: int, request_id: str,
                          question: str, output: str, status: CompletedStatus = "answered",
                          source_ids: Sequence[str] = ()) -> AppendResult: ...
    async def get_summary(self, session_id: str, *, expected_version: int) -> Summary: ...
    async def get_summary_work(self, session_id: str, *, expected_version: int) -> SummaryWork: ...
    async def update_summary(self, session_id: str, *, expected_version: int, text: str,
                             summarized_until_turn_id: int) -> SessionSnapshot: ...
    async def end_session(self, session_id: str) -> bool: ...
    async def purge_expired(self) -> int: ...


@dataclass
class _Session:
    session_id: str
    created_at: datetime
    last_active_at: datetime
    expires_at: datetime
    version: int = 0
    turns: list[Turn] = field(default_factory=list)
    requests: dict[str, Turn] = field(default_factory=dict)
    summary: Summary = field(default_factory=Summary)


def _identifier(value: str, name: str):
    if not isinstance(value, str) or not value.strip() or len(value) > 128:
        raise ValueError(f"{name} must be nonempty text of at most 128 characters")


def _version(value):
    if type(value) is not int or value < 0:
        raise ValueError("expected_version must be a nonnegative integer")


class InMemorySessionStore:
    """데모용 메모리 저장소. 같은 프로세스의 스레드 사이에서도 연산을 원자적으로 처리한다.

    공개 API는 비동기지만 내부 외부 I/O나 await 없이 짧은 연산을 RLock으로 보호한다.
    잠금 안에서 모델을 호출하지 않는다. 다른 프로세스·워커와 공유되지 않는다.
    """
    def __init__(self, *, ttl_seconds: float = 1800, recent_turn_limit: int = 5,
                 max_sessions: int = 1000, clock: Callable[[], datetime] | None = None):
        if (isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, (int, float))
                or not math.isfinite(ttl_seconds) or ttl_seconds <= 0):
            raise ValueError("ttl_seconds must be positive and finite")
        if type(recent_turn_limit) is not int or recent_turn_limit < 1:
            raise ValueError("recent_turn_limit must be a positive integer")
        if type(max_sessions) is not int or max_sessions < 1:
            raise ValueError("max_sessions must be a positive integer")
        try:
            self._ttl = timedelta(seconds=ttl_seconds)
        except OverflowError as exc:
            raise ValueError("ttl_seconds is too large") from exc
        if self._ttl <= timedelta(0):
            raise ValueError("ttl_seconds is below clock precision")
        self._recent_limit = recent_turn_limit
        self._max_sessions = max_sessions
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.RLock()

    def _now(self):
        now = self._clock()
        if not isinstance(now, datetime) or now.utcoffset() is None:
            raise ValueError("clock must return a timezone-aware datetime")
        return now.astimezone(timezone.utc)

    def _require(self, session_id, now):
        _identifier(session_id, "session_id")
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionNotFoundError("Session is unavailable")
        if session.expires_at <= now:
            del self._sessions[session_id]
            raise SessionNotFoundError("Session is unavailable")
        return session

    @staticmethod
    def _check_version(session, expected_version):
        _version(expected_version)
        if session.version != expected_version:
            raise SessionVersionConflict("Session changed; reload its snapshot")

    @staticmethod
    def _snapshot(session):
        return SessionSnapshot(session.session_id, session.version, tuple(session.turns),
                               session.summary, session.created_at, session.last_active_at, session.expires_at)

    def _touch(self, session, now):
        session.last_active_at = now
        session.expires_at = now + self._ttl

    def _purge(self, now):
        expired = [key for key, session in self._sessions.items() if session.expires_at <= now]
        for key in expired:
            del self._sessions[key]
        return len(expired)

    async def create_session(self):
        with self._lock:
            now = self._now()
            self._purge(now)
            if len(self._sessions) >= self._max_sessions:
                raise SessionCapacityError("Active session capacity reached")
            session_id = uuid.uuid4().hex
            while session_id in self._sessions:
                session_id = uuid.uuid4().hex
            session = _Session(session_id, now, now, now + self._ttl)
            self._sessions[session_id] = session
            return self._snapshot(session)

    async def get_session(self, session_id, *, touch=True):
        if type(touch) is not bool:
            raise ValueError("touch must be boolean")
        with self._lock:
            now = self._now()
            session = self._require(session_id, now)
            if touch:
                self._touch(session, now)
            return self._snapshot(session)

    async def get_context(self, session_id, *, touch=True):
        if type(touch) is not bool:
            raise ValueError("touch must be boolean")
        with self._lock:
            now = self._now()
            session = self._require(session_id, now)
            if touch:
                self._touch(session, now)
            target = max(0, len(session.turns) - self._recent_limit)
            return SessionContext(
                session.session_id, session.version, tuple(session.turns[-self._recent_limit:]),
                bool(session.summary.text), session.summary.summarized_until_turn_id, target,
                session.summary.summarized_until_turn_id == target, session.expires_at,
            )

    async def get_recent_turns(self, session_id):
        return (await self.get_context(session_id, touch=False)).recent_turns

    async def get_turn_by_request(self, session_id, request_id):
        _identifier(request_id, "request_id")
        with self._lock:
            return self._require(session_id, self._now()).requests.get(request_id)

    async def append_turn(self, session_id, *, expected_version, request_id, question,
                          output, status="answered", source_ids=()):
        """CAS로 완료 턴 저장. 동일 request_id·동일 결과의 재전송은 쓰기 전에 판정한다."""
        _version(expected_version)
        _identifier(request_id, "request_id")
        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must be nonempty text")
        if not isinstance(output, str) or not output.strip():
            raise ValueError("output must be nonempty text")
        if not isinstance(status, str) or status not in COMPLETED_STATUSES:
            raise ValueError("Only completed conversational responses can be stored")
        if not isinstance(source_ids, Sequence) or isinstance(source_ids, (str, bytes)):
            raise ValueError("source_ids must be a sequence of text IDs")
        sources = tuple(source_ids)
        if any(not isinstance(key, str) or not key.strip() for key in sources):
            raise ValueError("source_ids must contain nonempty text IDs")
        with self._lock:
            now = self._now()
            session = self._require(session_id, now)
            previous = session.requests.get(request_id)
            if previous is not None:
                if (previous.question, previous.output, previous.status, previous.source_ids) != (
                        question, output, status, sources):
                    raise RequestConflict("request_id already has a different completed result")
                self._touch(session, now)
                return AppendResult(session_id, session.version, previous, True)
            self._check_version(session, expected_version)
            turn = Turn(len(session.turns) + 1, request_id, question, output, status, sources, now)
            session.turns.append(turn)
            session.requests[request_id] = turn
            session.version += 1
            self._touch(session, now)
            return AppendResult(session_id, session.version, turn, False)

    async def get_summary(self, session_id, *, expected_version):
        with self._lock:
            session = self._require(session_id, self._now())
            self._check_version(session, expected_version)
            return session.summary

    async def get_summary_work(self, session_id, *, expected_version):
        """최근 범위 밖이면서 아직 요약하지 않은 연속 구간을 스냅샷으로 반환한다."""
        with self._lock:
            session = self._require(session_id, self._now())
            self._check_version(session, expected_version)
            target = max(0, len(session.turns) - self._recent_limit)
            cursor = session.summary.summarized_until_turn_id
            return SummaryWork(session_id, session.version, session.summary,
                               tuple(session.turns[cursor:target]), target)

    async def update_summary(self, session_id, *, expected_version, text, summarized_until_turn_id):
        """외부에서 생성한 누적 요약과 cursor를 같은 잠금·버전 갱신으로 저장한다.

        get_summary_work()가 반환한 전체 구간을 반영한 요약만 전달해야 한다.
        본문의 의미 보존은 생성·검증 계층의 책임이다. 실패한 생성은 이 메서드를 호출하지 않는다.
        """
        if not isinstance(text, str) or not text.strip():
            raise ValueError("summary text must be nonempty")
        if type(summarized_until_turn_id) is not int or summarized_until_turn_id < 1:
            raise ValueError("summary cursor must be a positive integer")
        with self._lock:
            now = self._now()
            session = self._require(session_id, now)
            self._check_version(session, expected_version)
            target = max(0, len(session.turns) - self._recent_limit)
            if (summarized_until_turn_id != target
                    or target <= session.summary.summarized_until_turn_id):
                raise ValueError("Summary must advance to the current pending range boundary")
            session.summary = Summary(text, target, now)
            session.version += 1
            # 요약 백그라운드 작업만으로 미사용 세션의 수명을 연장하지 않는다.
            return self._snapshot(session)

    async def end_session(self, session_id):
        _identifier(session_id, "session_id")
        with self._lock:
            now = self._now()
            session = self._sessions.pop(session_id, None)
            return session is not None and session.expires_at > now

    async def purge_expired(self):
        with self._lock:
            return self._purge(self._now())
