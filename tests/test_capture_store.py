"""Automated unit and persistence tests for Milestone 3 Task 18B: Quick Capture Storage.

Verifies:
1. Schema initialization (table, PRAGMA user_version, indexes)
2. All four CaptureType values (IDEA, JOURNAL, MOOD, REMEMBER)
3. save_capture() functionality and return values
4. get_capture() retrieval by ID
5. missing capture returns None
6. whitespace trimming
7. empty content rejection
8. content length validation (10,000 char threshold)
9. invalid capture type rejection
10. automatic UTC timestamp generation (ISO 8601 with 'Z')
11. explicit timestamp persistence and validation
12. list_recent() reverse-chronological ordering
13. list_recent() limit enforcement
14. list_recent() capture_type filtering
15. list_for_date_range() filtering and chronological ordering
16. count() accuracy
17. persistence across store close/reopen using temporary on-disk SQLite database
18. safe close behavior and operations blocked when closed
19. default Windows database path resolution
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from doodle.persistence.capture_store import (
    DEFAULT_MAX_CONTENT_LENGTH,
    CaptureRecord,
    CaptureStore,
    CaptureType,
    StorageError,
    generate_utc_timestamp,
    get_default_database_path,
)


class TestCaptureTypeModel(unittest.TestCase):
    """Unit tests for the CaptureType enum."""

    def test_all_four_capture_type_values(self) -> None:
        expected = {"IDEA", "JOURNAL", "MOOD", "REMEMBER"}
        actual = {t.value for t in CaptureType}
        self.assertEqual(actual, expected)
        self.assertEqual(len(list(CaptureType)), 4)

    def test_string_representation(self) -> None:
        self.assertEqual(str(CaptureType.IDEA), "IDEA")
        self.assertEqual(str(CaptureType.JOURNAL), "JOURNAL")
        self.assertEqual(str(CaptureType.MOOD), "MOOD")
        self.assertEqual(str(CaptureType.REMEMBER), "REMEMBER")


class TestCaptureStoreSchema(unittest.TestCase):
    """Unit tests verifying SQLite schema creation, versioning, and indexes."""

    def setUp(self) -> None:
        self.store = CaptureStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_schema_creation_and_version(self) -> None:
        conn = self.store._conn
        cursor = conn.cursor()

        # Check PRAGMA user_version
        cursor.execute("PRAGMA user_version;")
        version = cursor.fetchone()[0]
        self.assertEqual(version, 1)

        # Check captures table exists
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='captures';"
        )
        self.assertIsNotNone(cursor.fetchone())

        # Check table columns
        cursor.execute("PRAGMA table_info(captures);")
        columns = {row[1]: row[2].upper() for row in cursor.fetchall()}
        self.assertIn("id", columns)
        self.assertIn("capture_type", columns)
        self.assertIn("content", columns)
        self.assertIn("created_at", columns)

    def test_indexes_exist(self) -> None:
        conn = self.store._conn
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='captures';"
        )
        index_names = {row[0] for row in cursor.fetchall()}
        self.assertIn("idx_captures_created_at", index_names)
        self.assertIn("idx_captures_type_created", index_names)


class TestCaptureStoreOperations(unittest.TestCase):
    """Unit tests for CaptureStore CRUD, filtering, sorting, and validation."""

    def setUp(self) -> None:
        self.store = CaptureStore(":memory:")

    def tearDown(self) -> None:
        self.store.close()

    def test_save_and_get_capture(self) -> None:
        record = self.store.save_capture(
            capture_type=CaptureType.IDEA,
            content="Build a living companion desktop app",
        )
        self.assertIsInstance(record, CaptureRecord)
        self.assertEqual(record.id, 1)
        self.assertEqual(record.capture_type, CaptureType.IDEA)
        self.assertEqual(record.content, "Build a living companion desktop app")
        self.assertTrue(record.created_at.endswith("Z"))

        # Fetch by ID
        fetched = self.store.get_capture(1)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched, record)

    def test_missing_capture_returns_none(self) -> None:
        self.assertIsNone(self.store.get_capture(999))
        self.assertIsNone(self.store.get_capture(-1))

    def test_whitespace_trimming(self) -> None:
        record = self.store.save_capture(
            capture_type=CaptureType.JOURNAL,
            content="   \n\t  Wrapped up work for the evening.  \t\n  ",
        )
        self.assertEqual(record.content, "Wrapped up work for the evening.")

        fetched = self.store.get_capture(record.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.content, "Wrapped up work for the evening.")

    def test_empty_content_rejection(self) -> None:
        empty_inputs = ["", "   ", "\n\t  \r", "   \t   "]
        for empty in empty_inputs:
            with self.subTest(empty=repr(empty)):
                with self.assertRaises(ValueError) as ctx:
                    self.store.save_capture(CaptureType.IDEA, empty)
                self.assertIn("empty", str(ctx.exception).lower())

    def test_non_string_content_rejection(self) -> None:
        with self.assertRaises(ValueError):
            self.store.save_capture(CaptureType.IDEA, None)  # type: ignore

        with self.assertRaises(ValueError):
            self.store.save_capture(CaptureType.IDEA, 12345)  # type: ignore

    def test_content_length_validation(self) -> None:
        # Exactly 10,000 characters: valid
        max_content = "a" * DEFAULT_MAX_CONTENT_LENGTH
        record = self.store.save_capture(CaptureType.IDEA, max_content)
        self.assertEqual(len(record.content), DEFAULT_MAX_CONTENT_LENGTH)

        # 10,001 characters: exceeds limit, raises ValueError
        too_long = "a" * (DEFAULT_MAX_CONTENT_LENGTH + 1)
        with self.assertRaises(ValueError) as ctx:
            self.store.save_capture(CaptureType.IDEA, too_long)
        self.assertIn("exceeds maximum allowed length", str(ctx.exception))

    def test_invalid_capture_type_rejection(self) -> None:
        invalid_types = ["TODO", "TASK", "NOTE", "REMINDER", "INVALID", "", "idea_spark"]
        for bad_type in invalid_types:
            with self.subTest(bad_type=bad_type):
                with self.assertRaises(ValueError) as ctx:
                    self.store.save_capture(bad_type, "Test content")
                self.assertIn("Invalid capture type", str(ctx.exception))

    def test_automatic_utc_timestamp_generation(self) -> None:
        record = self.store.save_capture(CaptureType.MOOD, "Calm and peaceful")
        ts = record.created_at
        self.assertTrue(ts.endswith("Z"), f"Expected timestamp ending in Z, got {ts}")
        # Verify valid ISO 8601 parsing
        parsed = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        self.assertIsNotNone(parsed.tzinfo)

    def test_explicit_timestamp_persistence(self) -> None:
        explicit_ts = "2026-10-03T18:00:00.000000Z"
        record = self.store.save_capture(
            capture_type=CaptureType.REMEMBER,
            content="Call mentor tomorrow morning",
            created_at=explicit_ts,
        )
        self.assertEqual(record.created_at, explicit_ts)

        fetched = self.store.get_capture(record.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.created_at, explicit_ts)

    def test_invalid_explicit_timestamp_rejection(self) -> None:
        with self.assertRaises(ValueError):
            self.store.save_capture(CaptureType.IDEA, "Valid content", created_at="")
        with self.assertRaises(ValueError):
            self.store.save_capture(CaptureType.IDEA, "Valid content", created_at="   ")

    def test_list_recent_ordering_and_limit(self) -> None:
        # Insert 5 captures with explicitly ordered timestamps
        timestamps = [
            "2026-10-01T10:00:00.000000Z",
            "2026-10-02T10:00:00.000000Z",
            "2026-10-03T10:00:00.000000Z",
            "2026-10-04T10:00:00.000000Z",
            "2026-10-05T10:00:00.000000Z",
        ]
        for i, ts in enumerate(timestamps):
            self.store.save_capture(CaptureType.IDEA, f"Idea #{i + 1}", created_at=ts)

        # list_recent default: newest first
        all_recent = self.store.list_recent(limit=10)
        self.assertEqual(len(all_recent), 5)
        self.assertEqual(all_recent[0].content, "Idea #5")
        self.assertEqual(all_recent[4].content, "Idea #1")

        # list_recent with limit
        limited = self.store.list_recent(limit=2)
        self.assertEqual(len(limited), 2)
        self.assertEqual(limited[0].content, "Idea #5")
        self.assertEqual(limited[1].content, "Idea #4")

    def test_capture_type_filtering(self) -> None:
        self.store.save_capture(CaptureType.IDEA, "First idea")
        self.store.save_capture(CaptureType.JOURNAL, "First journal entry")
        self.store.save_capture(CaptureType.IDEA, "Second idea")
        self.store.save_capture(CaptureType.MOOD, "Good mood")
        self.store.save_capture(CaptureType.REMEMBER, "Remember this")

        # Filter by CaptureType.IDEA
        ideas = self.store.list_recent(capture_type=CaptureType.IDEA)
        self.assertEqual(len(ideas), 2)
        self.assertTrue(all(r.capture_type == CaptureType.IDEA for r in ideas))
        self.assertEqual(ideas[0].content, "Second idea")
        self.assertEqual(ideas[1].content, "First idea")

        # Filter by string "journal"
        journals = self.store.list_recent(capture_type="journal")
        self.assertEqual(len(journals), 1)
        self.assertEqual(journals[0].content, "First journal entry")

        # Empty result for type with no entries
        empty_store = CaptureStore(":memory:")
        self.assertEqual(empty_store.list_recent(capture_type=CaptureType.MOOD), [])
        empty_store.close()

    def test_date_range_filtering(self) -> None:
        self.store.save_capture(
            CaptureType.IDEA, "Past entry", created_at="2026-09-30T12:00:00.000000Z"
        )
        self.store.save_capture(
            CaptureType.JOURNAL, "Target Day morning", created_at="2026-10-01T08:00:00.000000Z"
        )
        self.store.save_capture(
            CaptureType.MOOD, "Target Day evening", created_at="2026-10-01T20:00:00.000000Z"
        )
        self.store.save_capture(
            CaptureType.REMEMBER, "Future entry", created_at="2026-10-02T12:00:00.000000Z"
        )

        range_captures = self.store.list_for_date_range(
            start_utc="2026-10-01T00:00:00.000000Z",
            end_utc="2026-10-01T23:59:59.999999Z",
        )
        # Should return Target Day entries in chronological order (oldest first for timelines)
        self.assertEqual(len(range_captures), 2)
        self.assertEqual(range_captures[0].content, "Target Day morning")
        self.assertEqual(range_captures[1].content, "Target Day evening")

    def test_count(self) -> None:
        self.assertEqual(self.store.count(), 0)
        self.store.save_capture(CaptureType.IDEA, "Idea 1")
        self.assertEqual(self.store.count(), 1)
        self.store.save_capture(CaptureType.JOURNAL, "Journal 1")
        self.assertEqual(self.store.count(), 2)


class TestCaptureStoreLifecycleAndPersistence(unittest.TestCase):
    """Persistence across store restart and connection lifecycle tests."""

    def test_persistence_after_close_and_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_file = Path(temp_dir) / "test_captures.db"

            # 1. Initialize store on disk, save records, then close
            store1 = CaptureStore(db_file)
            r1 = store1.save_capture(
                CaptureType.IDEA,
                "Persistent idea",
                created_at="2026-10-03T10:00:00.000000Z",
            )
            r2 = store1.save_capture(
                CaptureType.JOURNAL,
                "Persistent journal entry",
                created_at="2026-10-03T11:00:00.000000Z",
            )
            self.assertEqual(store1.count(), 2)
            store1.close()
            self.assertTrue(store1.is_closed)

            # 2. Re-open connection to same file
            store2 = CaptureStore(db_file)
            self.assertFalse(store2.is_closed)
            self.assertEqual(store2.count(), 2)

            fetched1 = store2.get_capture(r1.id)
            self.assertIsNotNone(fetched1)
            self.assertEqual(fetched1.content, "Persistent idea")
            self.assertEqual(fetched1.capture_type, CaptureType.IDEA)
            self.assertEqual(fetched1.created_at, "2026-10-03T10:00:00.000000Z")

            fetched2 = store2.get_capture(r2.id)
            self.assertIsNotNone(fetched2)
            self.assertEqual(fetched2.content, "Persistent journal entry")
            self.assertEqual(fetched2.capture_type, CaptureType.JOURNAL)

            recent = store2.list_recent()
            self.assertEqual(len(recent), 2)
            self.assertEqual(recent[0].id, r2.id)
            self.assertEqual(recent[1].id, r1.id)

            store2.close()

    def test_safe_close_behavior_and_blocked_operations(self) -> None:
        store = CaptureStore(":memory:")
        self.assertFalse(store.is_closed)

        store.close()
        self.assertTrue(store.is_closed)

        # Closing multiple times is safe and idempotent
        store.close()
        self.assertTrue(store.is_closed)

        # Operations on closed store must raise StorageError
        with self.assertRaises(StorageError):
            store.save_capture(CaptureType.IDEA, "Test")

        with self.assertRaises(StorageError):
            store.get_capture(1)

        with self.assertRaises(StorageError):
            store.list_recent()

        with self.assertRaises(StorageError):
            store.list_for_date_range("2026-01-01", "2026-01-02")

        with self.assertRaises(StorageError):
            store.count()

    def test_context_manager(self) -> None:
        with CaptureStore(":memory:") as store:
            record = store.save_capture(CaptureType.MOOD, "Feeling great")
            self.assertEqual(store.count(), 1)
        self.assertTrue(store.is_closed)

    def test_default_database_path(self) -> None:
        path = get_default_database_path()
        self.assertIsInstance(path, Path)
        self.assertEqual(path.name, "doodle_captures.db")
        self.assertEqual(path.parent.name, "Doodle")


if __name__ == "__main__":
    unittest.main()
