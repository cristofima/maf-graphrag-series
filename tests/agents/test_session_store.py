"""Unit tests for in-memory conversational session store behavior."""

from __future__ import annotations

import asyncio

import pytest
from agent_framework import AgentSession, InMemoryCheckpointStorage, WorkflowCheckpoint

from agents.session_store import InMemorySessionStore, SessionKey


class _Clock:
    def __init__(self, now: float = 0.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_session_key_normalization_and_deterministic_id() -> None:
    key_a = SessionKey.create(channel_id="  MSTeams  ", conversation_id=" conv-1 ", user_id=" USER-1 ")
    key_b = SessionKey.create(channel_id="msteams", conversation_id="conv-1", user_id="user-1")

    assert key_a.channel_id == "msteams"
    assert key_a.conversation_id == "conv-1"
    assert key_a.user_id == "user-1"
    assert key_a.session_id == key_b.session_id


async def test_ttl_expiration_removes_stale_session_and_counts_metric() -> None:
    clock = _Clock(10.0)
    store = InMemorySessionStore(
        ttl_seconds=5,
        max_count=10,
        cleanup_interval_seconds=100,
        max_history_groups=4,
        monotonic=clock,
    )
    key = SessionKey.create(channel_id="msteams", conversation_id="c1", user_id="u1")

    record, created = await store.get_or_create(key.session_id)

    assert created is True
    assert await store.get_record(key.session_id) is record

    clock.advance(6)
    assert await store.get_record(key.session_id) is None
    assert store.metrics.ttl_expirations == 1


async def test_capacity_eviction_removes_oldest_record() -> None:
    clock = _Clock(0.0)
    store = InMemorySessionStore(
        ttl_seconds=100,
        max_count=2,
        cleanup_interval_seconds=100,
        max_history_groups=4,
        monotonic=clock,
    )

    key1 = SessionKey.create(channel_id="msteams", conversation_id="c1", user_id="u1")
    key2 = SessionKey.create(channel_id="msteams", conversation_id="c2", user_id="u2")
    key3 = SessionKey.create(channel_id="msteams", conversation_id="c3", user_id="u3")

    await store.get_or_create(key1.session_id)
    clock.advance(1)
    await store.get_or_create(key2.session_id)
    clock.advance(1)
    await store.get_or_create(key3.session_id)

    assert await store.get_record(key1.session_id) is None
    assert await store.get_record(key2.session_id) is not None
    assert await store.get_record(key3.session_id) is not None
    assert store.metrics.evictions == 1


async def test_cleanup_interval_runs_and_updates_cleanup_metric() -> None:
    clock = _Clock(0.0)
    store = InMemorySessionStore(
        ttl_seconds=2,
        max_count=10,
        cleanup_interval_seconds=1,
        max_history_groups=4,
        monotonic=clock,
    )
    key = SessionKey.create(channel_id="msteams", conversation_id="c1", user_id="u1")

    await store.get_or_create(key.session_id)
    clock.advance(2)

    # Trigger opportunistic cleanup by touching the store.
    assert await store.get_record(key.session_id) is None
    assert store.metrics.cleanup_runs >= 1


async def test_append_turn_applies_sliding_window_and_compaction_diagnostics() -> None:
    store = InMemorySessionStore(
        ttl_seconds=100,
        max_count=10,
        cleanup_interval_seconds=100,
        max_history_groups=2,
    )
    key = SessionKey.create(channel_id="msteams", conversation_id="c1", user_id="u1")
    record, _ = await store.get_or_create(key.session_id)

    store.append_turn(record, user_text="u1", assistant_text="a1")
    store.append_turn(record, user_text="u2", assistant_text="a2")
    diagnostics = store.append_turn(record, user_text="u3", assistant_text="a3")

    assert record.turn_index == 3
    assert len(record.history_groups) == 2
    assert record.history_groups[0]["user"] == "u2"
    assert record.history_groups[1]["user"] == "u3"
    assert diagnostics.compacted is True
    assert diagnostics.compacted_groups == 1
    assert diagnostics.pre_count == 3
    assert diagnostics.post_count == 2


@pytest.mark.asyncio
async def test_native_workflow_checkpoint_storage_is_separate_from_history() -> None:
    store = InMemorySessionStore(
        ttl_seconds=100,
        max_count=10,
        cleanup_interval_seconds=100,
        max_history_groups=4,
    )
    key = SessionKey.create(channel_id="msteams", conversation_id="c1", user_id="u1")
    record, _ = await store.get_or_create(key.session_id)
    checkpoint_storage = InMemoryCheckpointStorage()
    checkpoint = WorkflowCheckpoint(workflow_name="router", graph_signature_hash="test-graph")
    checkpoint_id = await checkpoint_storage.save(checkpoint)
    record.active_checkpoint_id = str(checkpoint_id)

    assert record.history_groups == []
    assert record.active_checkpoint_id == str(checkpoint_id)
    restored = await checkpoint_storage.load(checkpoint_id)
    assert restored.workflow_name == "router"
    assert await checkpoint_storage.list_checkpoints(workflow_name="router")


@pytest.mark.asyncio
async def test_session_record_lock_serializes_same_session_writes() -> None:
    store = InMemorySessionStore(
        ttl_seconds=100,
        max_count=10,
        cleanup_interval_seconds=100,
        max_history_groups=8,
    )
    key = SessionKey.create(channel_id="msteams", conversation_id="c1", user_id="u1")
    record, _ = await store.get_or_create(key.session_id)

    timeline: list[str] = []

    async def worker(name: str) -> None:
        async with record.lock:
            timeline.append(f"start:{name}")
            await asyncio.sleep(0)
            timeline.append(f"end:{name}")

    await asyncio.gather(worker("one"), worker("two"))

    assert timeline in (
        ["start:one", "end:one", "start:two", "end:two"],
        ["start:two", "end:two", "start:one", "end:one"],
    )


@pytest.mark.asyncio
async def test_native_session_store_get_set_delete_roundtrip() -> None:
    """Locks down the inherited SessionStore async contract (get/set/delete).

    Per SessionStore's documented contract, get() returns an independent
    deep copy, so we assert on session_id equality rather than identity.
    """
    store = InMemorySessionStore(
        ttl_seconds=100,
        max_count=10,
        cleanup_interval_seconds=100,
        max_history_groups=4,
    )
    session = AgentSession(session_id="native-session-1")

    assert await store.get("native-session-1") is None

    await store.set("native-session-1", session)
    fetched = await store.get("native-session-1")
    assert fetched is not None
    assert fetched.session_id == "native-session-1"

    await store.delete("native-session-1")
    assert await store.get("native-session-1") is None


@pytest.mark.asyncio
async def test_native_session_store_get_expires_with_ttl() -> None:
    clock = _Clock(0.0)
    store = InMemorySessionStore(
        ttl_seconds=5,
        max_count=10,
        cleanup_interval_seconds=100,
        max_history_groups=4,
        monotonic=clock,
    )
    session = AgentSession(session_id="native-session-2")

    await store.set("native-session-2", session)
    clock.advance(6)

    assert await store.get("native-session-2") is None
    assert store.metrics.ttl_expirations >= 1


@pytest.mark.asyncio
async def test_capacity_eviction_removes_native_session_and_record() -> None:
    clock = _Clock(0.0)
    store = InMemorySessionStore(
        ttl_seconds=100,
        max_count=1,
        cleanup_interval_seconds=100,
        max_history_groups=4,
        monotonic=clock,
    )

    first = AgentSession(session_id="native-session-first")
    second = AgentSession(session_id="native-session-second")
    await store.set(first.session_id, first)
    clock.advance(1)
    await store.set(second.session_id, second)

    assert await store.get_record(first.session_id) is None
    assert await store.get(first.session_id) is None
    assert await store.get_record(second.session_id) is not None
    assert await store.get(second.session_id) is not None
    assert store.metrics.evictions == 1
