"""Session store with TTL, bounded capacity, and automatic cleanup.

This module provides InMemorySessionStore, which extends agent_framework's SessionStore
protocol with production-ready TTL, LRU eviction, and periodic cleanup—following
Microsoft's recommended pattern for custom session storage implementations.

Ref: https://learn.microsoft.com/agent-framework/hosting/self-hosting/
> "Subclass it and override those methods to store AgentSession objects..."

ARCHITECTURE NOTE:
- InMemorySessionStore (this file) extends SessionStore (native framework)
- SessionRecord is a data container (not framework-mandated)
- AppendTurn diagnostics are returned for observability
- History compaction is delegated to calling code for flexibility
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
import warnings
from collections.abc import Callable
from dataclasses import dataclass, field

from agent_framework import AgentSession, SessionStore
from agent_framework._feature_stage import ExperimentalWarning  # no public alias exists

logger = logging.getLogger(__name__)

# SessionStore is an accepted experimental dependency (see ARCHITECTURE NOTE above).
# Its __init_subclass__ hook warns at class-definition time, which would otherwise
# fail collection under warnings-as-errors CI gates regardless of pytest config.
warnings.filterwarnings("ignore", category=ExperimentalWarning, module=r"agents\.session_store")


@dataclass(frozen=True, slots=True)
class SessionKey:
    """Stable session identity for a conversation participant on a channel.

    This class is maintained for backward compatibility with existing code.
    The actual session_id (str) is derived from channel, conversation, and user IDs.
    """

    channel_id: str
    conversation_id: str
    user_id: str

    @classmethod
    def create(cls, *, channel_id: str, conversation_id: str, user_id: str) -> SessionKey:
        """Build a normalized key from transport values."""
        return cls(
            channel_id=channel_id.strip().lower() or "unknown-channel",
            conversation_id=conversation_id.strip() or "unknown-conversation",
            user_id=user_id.strip().lower() or "unknown-user",
        )

    @property
    def session_id(self) -> str:
        """Return a deterministic compact identifier safe for logs and headers."""
        fingerprint = f"{self.channel_id}|{self.conversation_id}|{self.user_id}".encode()
        # SHA256 truncated to 32 chars (128 bits, mitigates collision risk vs 16 char)
        return hashlib.sha256(fingerprint).hexdigest()[:32]


@dataclass(slots=True)
class SessionCompactionDiagnostics:
    """Structured diagnostics from history compaction operation."""

    compacted: bool = False
    compacted_groups: int = 0
    pre_count: int = 0
    post_count: int = 0


@dataclass(slots=True)
class SessionRecord:
    """Backward-compatibility wrapper for session metadata and history.

    This is NOT a framework type; it's an application-specific data structure
    that holds mutable state alongside the AgentSession stored in framework.
    """

    session_id: str
    created_at_monotonic: float
    updated_at_monotonic: float
    expires_at_monotonic: float
    turn_index: int = 0
    history_groups: list[dict[str, str]] = field(default_factory=list)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    diagnostics: SessionCompactionDiagnostics = field(default_factory=SessionCompactionDiagnostics)
    # Correlates this record with a native workflow checkpoint without duplicating checkpoint storage.
    active_checkpoint_id: str | None = None


@dataclass(slots=True)
class SessionStoreMetrics:
    """Operational counters for session lifecycle behavior."""

    active_sessions: int = 0
    evictions: int = 0
    ttl_expirations: int = 0
    cleanup_runs: int = 0


class InMemorySessionStore(SessionStore):
    """SessionStore subclass with TTL, bounded capacity, and cleanup.

    EXTENDS: agent_framework.SessionStore
    ADDS: TTL expiration, LRU eviction, periodic cleanup

    Usage pattern:
        store = InMemorySessionStore(
            ttl_seconds=1800,
            max_count=1000,
            cleanup_interval_seconds=60,
            max_history_groups=50,
        )

        # Bootstrap or retrieve session
        record, created = await store.get_or_create(session_id)

        # Append turn with history management
        diagnostics = store.append_turn(
            record,
            user_text="Hello",
            assistant_text="Hi there!",
        )
    """

    def __init__(
        self,
        *,
        ttl_seconds: int,
        max_count: int,
        cleanup_interval_seconds: int,
        max_history_groups: int,
        monotonic: Callable[[], float] | None = None,
    ) -> None:
        """Initialize TTL-aware session store.

        Args:
            ttl_seconds: Session expiration time (seconds)
            max_count: Maximum active sessions
            cleanup_interval_seconds: How often to run cleanup
            max_history_groups: Max user-assistant turn pairs
            monotonic: Clock function (for testing)

        Raises:
            ValueError: If parameters are out of valid range
        """
        super().__init__()

        # Validation
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be > 0")
        if max_count <= 0:
            raise ValueError("max_count must be > 0")
        if cleanup_interval_seconds <= 0:
            raise ValueError("cleanup_interval_seconds must be > 0")
        if max_history_groups <= 0:
            raise ValueError("max_history_groups must be > 0")

        self._ttl_seconds = ttl_seconds
        self._max_count = max_count
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._max_history_groups = max_history_groups
        self._clock = monotonic or time.monotonic

        self._records: dict[str, SessionRecord] = {}
        self._metrics = SessionStoreMetrics()
        self._last_cleanup_monotonic = self._clock()

    @property
    def metrics(self) -> SessionStoreMetrics:
        """Return a snapshot of operational metrics."""
        self._metrics.active_sessions = len(self._records)
        return self._metrics

    # ========================================================================
    # SessionStore protocol implementation
    # ========================================================================

    async def get(self, session_id: str) -> AgentSession | None:
        """Get AgentSession, checking TTL and refreshing expiration."""
        await self._run_cleanup_if_needed()

        # For backward compat, we maintain both:
        # - Parent class storage (_sessions dict from framework)
        # - Our _records dict for SessionRecord metadata

        session = await super().get(session_id)
        if session is None:
            return None

        record = self._records.get(session_id)
        now = self._clock()

        if record is not None and record.expires_at_monotonic <= now:
            await super().delete(session_id)
            del self._records[session_id]
            self._metrics.ttl_expirations += 1
            logger.debug("Session %s expired (TTL)", session_id)
            return None

        if record is not None:
            self._refresh_record(record, now)

        self._metrics.active_sessions = len(self._records)
        return session

    async def set(self, session_id: str, session: AgentSession) -> None:
        """Set AgentSession and track metadata."""
        await self._run_cleanup_if_needed()
        now = self._clock()

        # Ensure we have a SessionRecord for this session_id
        if session_id not in self._records:
            self._records[session_id] = SessionRecord(
                session_id=session_id,
                created_at_monotonic=now,
                updated_at_monotonic=now,
                expires_at_monotonic=now + self._ttl_seconds,
            )
        else:
            self._refresh_record(self._records[session_id], now)

        await super().set(session_id, session)
        await self._enforce_capacity(skip_session_id=session_id)
        self._metrics.active_sessions = len(self._records)

    async def delete(self, session_id: str) -> None:
        """Delete session and metadata."""
        if session_id in self._records:
            del self._records[session_id]

        await super().delete(session_id)
        self._metrics.active_sessions = len(self._records)

    # ========================================================================
    # Application convenience methods
    # ========================================================================

    async def get_record(self, session_id: str) -> SessionRecord | None:
        """Return the live SessionRecord for *session_id*, or None if absent/expired.

        Unlike ``get_or_create``, this never creates a new record; it is a read-only
        peek used by callers that only want to inspect existing session state.
        """
        await self._run_cleanup_if_needed()
        record = self._records.get(session_id)
        if record is None:
            return None

        now = self._clock()
        if record.expires_at_monotonic <= now:
            del self._records[session_id]
            await super().delete(session_id)
            self._metrics.ttl_expirations += 1
            logger.debug(f"Session {session_id} expired (TTL)")
            self._metrics.active_sessions = len(self._records)
            return None

        self._refresh_record(record, now)
        self._metrics.active_sessions = len(self._records)
        return record

    async def get_or_create(self, session_id: str) -> tuple[SessionRecord, bool]:
        """Return existing record or create one. Bool=True if created.

        Cleanup and eviction are async so native AgentSession entries remain in sync.
        """
        await self._run_cleanup_if_needed()
        existing = self._records.get(session_id)
        if existing is not None:
            now = self._clock()
            if existing.expires_at_monotonic > now:
                self._refresh_record(existing, now)
                self._metrics.active_sessions = len(self._records)
                return existing, False
            else:
                # Expired
                del self._records[session_id]
                await super().delete(session_id)
                self._metrics.ttl_expirations += 1
            logger.debug("Session %s expired during get_or_create", session_id)
        now = self._clock()
        created = SessionRecord(
            session_id=session_id,
            created_at_monotonic=now,
            updated_at_monotonic=now,
            expires_at_monotonic=now + self._ttl_seconds,
        )
        self._records[session_id] = created
        await self._enforce_capacity(skip_session_id=session_id)
        self._metrics.active_sessions = len(self._records)
        return created, True

    def append_turn(
        self, record: SessionRecord, *, user_text: str, assistant_text: str
    ) -> SessionCompactionDiagnostics:
        """Append a turn to history and apply compaction if needed.

        NOTE: This is SYNC to maintain backward compatibility.
        """
        record.turn_index += 1
        record.history_groups.append({"user": user_text, "assistant": assistant_text})

        pre_count = len(record.history_groups)
        compacted_groups = 0

        if pre_count > self._max_history_groups:
            compacted_groups = pre_count - self._max_history_groups
            record.history_groups = record.history_groups[-self._max_history_groups :]
            logger.debug(
                "Session %s: compacted %d groups, keeping %d",
                record.session_id,
                compacted_groups,
                len(record.history_groups),
            )

        diagnostics = SessionCompactionDiagnostics(
            compacted=compacted_groups > 0,
            compacted_groups=compacted_groups,
            pre_count=pre_count,
            post_count=len(record.history_groups),
        )
        record.diagnostics = diagnostics

        now = self._clock()
        self._refresh_record(record, now)
        self._records[record.session_id] = record
        self._metrics.active_sessions = len(self._records)
        return diagnostics

    # ========================================================================
    # Private helpers
    # ========================================================================

    def _refresh_record(self, record: SessionRecord, now: float) -> None:
        """Update record timestamps (expiration and access time)."""
        record.updated_at_monotonic = now
        record.expires_at_monotonic = now + self._ttl_seconds

    async def _run_cleanup_if_needed(self) -> None:
        """Run cleanup periodically if needed."""
        now = self._clock()
        if now - self._last_cleanup_monotonic < self._cleanup_interval_seconds:
            return

        self._last_cleanup_monotonic = now
        self._metrics.cleanup_runs += 1

        expired_keys = [key for key, record in self._records.items() if record.expires_at_monotonic <= now]

        for key in expired_keys:
            del self._records[key]
            await super().delete(key)

        if expired_keys:
            self._metrics.ttl_expirations += len(expired_keys)
            logger.debug("Cleanup: expired %d sessions", len(expired_keys))

        await self._enforce_capacity()
        self._metrics.active_sessions = len(self._records)

    async def _enforce_capacity(self, skip_session_id: str | None = None) -> None:
        """Evict LRU sessions if over capacity."""
        while len(self._records) > self._max_count:
            candidates = [
                (key, record)
                for key, record in self._records.items()
                if key != skip_session_id or len(self._records) > 1
            ]

            if not candidates:
                break

            evict_key, _ = min(candidates, key=lambda item: item[1].updated_at_monotonic)
            del self._records[evict_key]
            await super().delete(evict_key)
            self._metrics.evictions += 1
            logger.debug("Capacity eviction: removed %s", evict_key)
