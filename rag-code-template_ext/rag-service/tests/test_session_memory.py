"""외부 서비스 없이 실제 메모리 저장소의 수명·CAS·요약 경계를 검증한다."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from session_memory import (
    InMemorySessionStore, RequestConflict, SessionCapacityError,
    SessionNotFoundError, SessionStore, SessionVersionConflict,
)


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 23, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += timedelta(seconds=seconds)


class SessionMemoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.clock = Clock()
        self.store = InMemorySessionStore(ttl_seconds=60, clock=self.clock)
        self.session = await self.store.create_session()

    async def append(self, question="질문", output="답변", request_id=None):
        snapshot = await self.store.get_session(self.session.session_id, touch=False)
        return await self.store.append_turn(snapshot.session_id, expected_version=snapshot.version,
                                            request_id=request_id or f"r{len(snapshot.turns) + 1}",
                                            question=question, output=output)

    async def add_turns(self, count):
        for i in range(count):
            await self.append(f"질문 {i + 1}", f"답변 {i + 1}")

    async def test_protocol_and_new_session(self):
        self.assertIsInstance(self.store, SessionStore)
        self.assertEqual(self.session.version, 0)
        self.assertEqual(self.session.turns, ())
        self.assertEqual(self.session.summary.summarized_until_turn_id, 0)
        context = await self.store.get_context(self.session.session_id)
        self.assertTrue(context.summary_is_current)
        self.assertFalse(context.summary_available)

    async def test_sessions_are_separate_even_with_same_request_id(self):
        other = await self.store.create_session()
        await self.append(request_id="same")
        result = await self.store.append_turn(other.session_id, expected_version=0, request_id="same",
                                             question="다른 질문", output="다른 답변")
        self.assertEqual(result.turn.turn_id, 1)
        self.assertEqual((await self.store.get_recent_turns(self.session.session_id))[0].question, "질문")

    async def test_recent_five_preserves_all_raw_turns(self):
        await self.add_turns(8)
        full = await self.store.get_session(self.session.session_id)
        recent = await self.store.get_recent_turns(full.session_id)
        self.assertEqual(len(full.turns), 8)
        self.assertEqual([t.turn_id for t in recent], [4, 5, 6, 7, 8])
        self.assertEqual([t.question for t in recent], [f"질문 {i}" for i in range(4, 9)])

    async def test_five_six_and_eight_turn_summary_boundaries(self):
        await self.add_turns(5)
        snapshot = await self.store.get_session(self.session.session_id)
        work = await self.store.get_summary_work(snapshot.session_id, expected_version=snapshot.version)
        self.assertEqual(work.turns, ())
        self.assertEqual(work.target_until_turn_id, 0)
        await self.append()
        context = await self.store.get_context(snapshot.session_id)
        self.assertFalse(context.summary_is_current)
        self.assertEqual(context.summary_target_until_turn_id, 1)
        snapshot = await self.store.update_summary(snapshot.session_id, expected_version=context.version,
                                                   text="1턴의 요약", summarized_until_turn_id=1)
        self.assertEqual(snapshot.version, 7)  # 6회 추가 + 요약 저장 1회
        seventh = await self.append()
        self.assertEqual(seventh.turn.turn_id, 7)  # version과 turn_id는 다름
        await self.append()
        snapshot = await self.store.get_session(snapshot.session_id)
        work = await self.store.get_summary_work(snapshot.session_id, expected_version=snapshot.version)
        self.assertEqual([t.turn_id for t in work.turns], [2, 3])
        self.assertEqual(work.previous_summary.text, "1턴의 요약")
        self.assertEqual(work.target_until_turn_id, 3)
        updated = await self.store.update_summary(snapshot.session_id, expected_version=work.version,
                                                  text="1~3턴의 누적 요약", summarized_until_turn_id=3)
        next_work = await self.store.get_summary_work(snapshot.session_id, expected_version=updated.version)
        self.assertEqual(next_work.turns, ())
        self.assertTrue((await self.store.get_context(snapshot.session_id)).summary_is_current)

    async def test_summary_rejects_recent_turns_regression_and_incomplete_range(self):
        await self.add_turns(8)
        for target in [0, 1, 2, 4, 8, True]:
            snapshot = await self.store.get_session(self.session.session_id)
            with self.subTest(target=target), self.assertRaises(ValueError):
                await self.store.update_summary(snapshot.session_id, expected_version=snapshot.version,
                                                text="invalid", summarized_until_turn_id=target)
        snapshot = await self.store.get_session(self.session.session_id)
        updated = await self.store.update_summary(snapshot.session_id, expected_version=snapshot.version,
                                                  text="valid", summarized_until_turn_id=3)
        with self.assertRaises(ValueError):
            await self.store.update_summary(snapshot.session_id, expected_version=updated.version,
                                            text="repeated", summarized_until_turn_id=3)

    async def test_summary_failure_or_invalid_input_does_not_advance_cursor(self):
        await self.add_turns(6)
        snapshot = await self.store.get_session(self.session.session_id)
        await self.store.get_summary_work(snapshot.session_id, expected_version=snapshot.version)
        # 외부 요약 생성 실패를 가정해 저장하지 않음. 빈 결과의 저장도 거부해야 함.
        with self.assertRaises(ValueError):
            await self.store.update_summary(snapshot.session_id, expected_version=snapshot.version,
                                            text=" ", summarized_until_turn_id=1)
        after = await self.store.get_session(snapshot.session_id, touch=False)
        self.assertEqual(after, snapshot)

    async def test_stale_summary_cannot_overwrite_newer_turn(self):
        await self.add_turns(6)
        snapshot = await self.store.get_session(self.session.session_id)
        work = await self.store.get_summary_work(snapshot.session_id, expected_version=snapshot.version)
        await self.append()
        with self.assertRaises(SessionVersionConflict):
            await self.store.update_summary(snapshot.session_id, expected_version=work.version,
                                            text="stale", summarized_until_turn_id=work.target_until_turn_id)
        current = await self.store.get_session(snapshot.session_id)
        self.assertEqual(current.summary.text, "")
        self.assertEqual(len(current.turns), 7)

    async def test_lazy_summary_read_checks_snapshot_version(self):
        context = await self.store.get_context(self.session.session_id)
        await self.append()
        with self.assertRaises(SessionVersionConflict):
            await self.store.get_summary(context.session_id, expected_version=context.version)

    async def test_same_request_same_result_is_idempotent_even_with_old_version(self):
        original = await self.append(request_id="idempotent")
        await self.append(request_id="later")
        duplicate = await self.store.append_turn(self.session.session_id, expected_version=0,
                                                  request_id="idempotent", question="질문", output="답변")
        self.assertTrue(duplicate.duplicate)
        self.assertEqual(duplicate.turn, original.turn)
        self.assertEqual(duplicate.version, 2)
        self.assertEqual(len((await self.store.get_session(self.session.session_id)).turns), 2)
        self.assertEqual(await self.store.get_turn_by_request(self.session.session_id, "idempotent"), original.turn)
        self.assertIsNone(await self.store.get_turn_by_request(self.session.session_id, "missing"))

    async def test_request_payload_conflict_preserves_original(self):
        original = await self.append(request_id="same")
        with self.assertRaises(RequestConflict):
            await self.store.append_turn(self.session.session_id, expected_version=0,
                                         request_id="same", question="질문", output="다른 답변")
        self.assertEqual(await self.store.get_turn_by_request(self.session.session_id, "same"), original.turn)

    async def test_different_stale_request_does_not_append(self):
        await self.append()
        with self.assertRaises(SessionVersionConflict):
            await self.store.append_turn(self.session.session_id, expected_version=0,
                                         request_id="stale", question="질문", output="답변")
        self.assertEqual(len((await self.store.get_session(self.session.session_id)).turns), 1)

    async def test_immutable_snapshots_and_copied_source_ids(self):
        source_ids = ["c1"]
        result = await self.store.append_turn(self.session.session_id, expected_version=0, request_id="r",
                                               question=" 원문 질문 ", output=" 원문 답변 ", source_ids=source_ids)
        source_ids.append("c2")
        self.assertEqual(result.turn.source_ids, ("c1",))
        self.assertEqual(result.turn.question, " 원문 질문 ")
        with self.assertRaises(FrozenInstanceError):
            result.turn.output = "changed"
        self.assertEqual(self.session.turns, ())  # 예전 스냅샷도 변하지 않음

    async def test_idle_expiration_cannot_be_resurrected(self):
        await self.append()
        self.clock.advance(60)
        with self.assertRaises(SessionNotFoundError):
            await self.store.get_session(self.session.session_id)
        with self.assertRaises(SessionNotFoundError):
            await self.store.append_turn(self.session.session_id, expected_version=0,
                                         request_id="r1", question="질문", output="답변")

    async def test_touch_refreshes_idle_expiry_without_content_version_change(self):
        self.clock.advance(50)
        context = await self.store.get_context(self.session.session_id)
        self.assertEqual(context.version, 0)
        self.clock.advance(20)
        self.assertEqual((await self.store.get_session(self.session.session_id, touch=False)).version, 0)
        self.clock.advance(40)
        with self.assertRaises(SessionNotFoundError):
            await self.store.get_session(self.session.session_id)

    async def test_summary_reads_and_updates_do_not_extend_idle_lifetime(self):
        await self.add_turns(6)
        self.clock.advance(50)
        work = await self.store.get_summary_work(self.session.session_id, expected_version=6)
        result = await self.store.update_summary(self.session.session_id, expected_version=work.version,
                                                 text="요약", summarized_until_turn_id=1)
        await self.store.get_summary(self.session.session_id, expected_version=result.version)
        self.clock.advance(10)
        with self.assertRaises(SessionNotFoundError):
            await self.store.get_recent_turns(self.session.session_id)

    async def test_end_and_purge(self):
        self.assertTrue(await self.store.end_session(self.session.session_id))
        self.assertFalse(await self.store.end_session(self.session.session_id))
        with self.assertRaises(SessionNotFoundError):
            await self.store.get_summary(self.session.session_id, expected_version=0)
        await self.store.create_session()
        await self.store.create_session()
        self.clock.advance(60)
        self.assertEqual(await self.store.purge_expired(), 2)
        self.assertEqual(await self.store.purge_expired(), 0)

    async def test_capacity_cleans_expired_without_evicting_active_sessions(self):
        store = InMemorySessionStore(ttl_seconds=60, max_sessions=1, clock=self.clock)
        first = await store.create_session()
        with self.assertRaises(SessionCapacityError):
            await store.create_session()
        self.clock.advance(60)
        second = await store.create_session()
        self.assertNotEqual(first.session_id, second.session_id)
        with self.assertRaises(SessionNotFoundError):
            await store.get_session(first.session_id)

    async def test_noncompleted_status_and_invalid_inputs_rejected(self):
        for status in ["error", "cancelled", "unknown"]:
            with self.assertRaises(ValueError):
                await self.store.append_turn(self.session.session_id, expected_version=0, request_id="r",
                                             question="q", output="a", status=status)
        for changes in [{"expected_version": True}, {"question": " "}, {"output": ""},
                        {"request_id": ""}, {"source_ids": "c1"}]:
            args = {"expected_version": 0, "request_id": "r", "question": "q", "output": "a", **changes}
            with self.assertRaises(ValueError):
                await self.store.append_turn(self.session.session_id, **args)
        self.assertEqual((await self.store.get_session(self.session.session_id)).version, 0)

    async def test_custom_recent_limit(self):
        store = InMemorySessionStore(recent_turn_limit=2)
        s = await store.create_session()
        for i in range(3):
            result = await store.append_turn(s.session_id, expected_version=i, request_id=str(i), question="q", output="a")
        self.assertEqual(len(await store.get_recent_turns(s.session_id)), 2)
        work = await store.get_summary_work(s.session_id, expected_version=result.version)
        self.assertEqual([t.turn_id for t in work.turns], [1])

    async def test_configuration_and_clock_validation(self):
        for kwargs in [{"ttl_seconds": 0}, {"ttl_seconds": float("inf")}, {"ttl_seconds": True},
                       {"ttl_seconds": 1e-12}, {"max_sessions": 0}, {"recent_turn_limit": True}]:
            with self.assertRaises(ValueError):
                InMemorySessionStore(**kwargs)
        with self.assertRaises(ValueError):
            await InMemorySessionStore(clock=lambda: datetime(2026, 10, 23)).create_session()


class ConcurrentMemoryTests(unittest.TestCase):
    def test_real_threads_compete_with_one_version(self):
        store = InMemorySessionStore()
        session = asyncio.run(store.create_session())
        barrier = threading.Barrier(2)

        def append(request_id):
            barrier.wait(timeout=5)
            try:
                return asyncio.run(store.append_turn(session.session_id, expected_version=0,
                                      request_id=request_id, question="q", output="a"))
            except SessionVersionConflict:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(append, ["a", "b"]))
        self.assertEqual(sum(r is not None for r in results), 1)
        self.assertEqual(len(asyncio.run(store.get_session(session.session_id)).turns), 1)

    def test_same_request_from_threads_commits_once(self):
        store = InMemorySessionStore()
        session = asyncio.run(store.create_session())
        barrier = threading.Barrier(2)

        def append(_):
            barrier.wait(timeout=5)
            return asyncio.run(store.append_turn(session.session_id, expected_version=0,
                              request_id="same", question="q", output="a"))

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(append, range(2)))
        self.assertEqual(sorted(r.duplicate for r in results), [False, True])
        self.assertEqual(len(asyncio.run(store.get_session(session.session_id)).turns), 1)


if __name__ == "__main__":
    unittest.main()
