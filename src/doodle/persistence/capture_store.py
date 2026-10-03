"""SQLite-backed persistence for Doodle Quick Captures.

Provides local-first, lightweight, structured storage for user thoughts,
journal moments, mood checkpoints, and memory anchors.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional, Sequence, Union

logger = logging.getLogger(__name__)

# Constants
DEFAULT_MAX_CONTENT_LENGTH: int = 10000
SCHEMA_VERSION: int = 1


class StorageError(Exception):
    """Raised when an operation on the CaptureStore fails."""


class CaptureType(str, Enum):
    """Supported conceptual categories for Quick Capture entries."""

    IDEA = "IDEA"
    JOURNAL = "JOURNAL"
    MOOD = "MOOD"
    REMEMBER = "REMEMBER"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class CaptureRecord:
    """Immutable representation of a persisted Quick Capture entry."""

    id: Optional[int]
    capture_type: CaptureType
    content: str
    created_at: str


def get_default_database_path() -> Path:
    """Return the platform-appropriate default SQLite database path.

    On Windows, resolves to %APPDATA%/Doodle/doodle_captures.db.
    """
    app_data = os.environ.get("APPDATA")
    if app_data:
        base_dir = Path(app_data)
    else:
        base_dir = Path.home() / "AppData" / "Roaming"
    return base_dir / "Doodle" / "doodle_captures.db"


def generate_utc_timestamp() -> str:
    """Generate an ISO 8601 UTC timestamp string with explicit 'Z' indicator."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CaptureStore:
    """SQLite-backed storage manager for Quick Captures.

    Follows a simple, local-first architecture:
        CaptureStore -> SQLite

    Features:
    - Zero external dependencies (uses standard library sqlite3).
    - In-memory (":memory:") support for fast, isolated unit tests.
    - Automatic schema and index initialization on creation.
    - Validation of capture types, content length, and non-empty content.
    - Chronological indexing for fast timeline lookups.
    """

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        """Initialize the CaptureStore with an optional path or in-memory target."""
        self._is_closed: bool = False

        if db_path is None:
            self._db_path: Union[str, Path] = get_default_database_path()
        elif db_path == ":memory:":
            self._db_path = ":memory:"
        else:
            self._db_path = Path(db_path)

        try:
            if isinstance(self._db_path, Path):
                self._db_path.parent.mkdir(parents=True, exist_ok=True)
                self._conn = sqlite3.connect(str(self._db_path))
            else:
                self._conn = sqlite3.connect(":memory:")

            self._conn.execute("PRAGMA foreign_keys = ON;")
            self._init_schema()
        except (sqlite3.Error, OSError) as exc:
            logger.error("Failed to initialize SQLite database at %s: %s", self._db_path, exc)
            raise StorageError(f"Failed to initialize SQLite database at {self._db_path}: {exc}") from exc

    @property
    def db_path(self) -> Union[Path, str]:
        """Return the database path or target."""
        return self._db_path

    @property
    def is_closed(self) -> bool:
        """Return True if the database connection has been closed."""
        return self._is_closed

    def _ensure_open(self) -> None:
        """Raise StorageError if the connection is closed."""
        if self._is_closed:
            raise StorageError("CaptureStore connection is closed.")

    def _init_schema(self) -> None:
        """Initialize schema, tables, and indexes if they do not already exist."""
        cursor = self._conn.cursor()
        cursor.execute("PRAGMA user_version = 1;")
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS captures (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                capture_type TEXT NOT NULL CHECK(
                    capture_type IN ('IDEA', 'JOURNAL', 'MOOD', 'REMEMBER')
                ),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_captures_created_at
            ON captures (created_at DESC);
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_captures_type_created
            ON captures (capture_type, created_at DESC);
            """
        )
        self._conn.commit()

    @staticmethod
    def _validate_capture_type(capture_type: Union[CaptureType, str]) -> CaptureType:
        """Validate and convert capture type to a valid CaptureType enum member."""
        if isinstance(capture_type, CaptureType):
            return capture_type
        if isinstance(capture_type, str):
            try:
                return CaptureType(capture_type.upper().strip())
            except ValueError:
                valid_types = [t.value for t in CaptureType]
                raise ValueError(
                    f"Invalid capture type: {capture_type!r}. Must be one of {valid_types}."
                )
        raise ValueError(
            f"Capture type must be a CaptureType or string, got {type(capture_type).__name__}."
        )

    def save_capture(
        self,
        capture_type: Union[CaptureType, str],
        content: str,
        created_at: Optional[str] = None,
    ) -> CaptureRecord:
        """Validate and persist a new Quick Capture entry.

        Args:
            capture_type: Category (IDEA, JOURNAL, MOOD, REMEMBER).
            content: User text (whitespace trimmed, non-empty, max 10,000 chars).
            created_at: Optional explicit ISO 8601 UTC timestamp string.

        Returns:
            The saved CaptureRecord with its assigned primary key ID.

        Raises:
            ValueError: If validation fails (invalid type, empty content, content too long).
            StorageError: If database write fails or store is closed.
        """
        self._ensure_open()

        # 1. Validate capture type
        validated_type = self._validate_capture_type(capture_type)

        # 2. Validate and trim content
        if not isinstance(content, str):
            raise ValueError(f"Content must be a string, got {type(content).__name__}.")

        trimmed = content.strip()
        if not trimmed:
            raise ValueError("Capture content cannot be empty.")

        if len(trimmed) > DEFAULT_MAX_CONTENT_LENGTH:
            raise ValueError(
                f"Capture content exceeds maximum allowed length of "
                f"{DEFAULT_MAX_CONTENT_LENGTH} characters (received {len(trimmed)})."
            )

        # 3. Resolve timestamp
        if created_at is None:
            ts = generate_utc_timestamp()
        else:
            if not isinstance(created_at, str) or not created_at.strip():
                raise ValueError("Explicit created_at timestamp must be a non-empty string.")
            ts = created_at.strip()

        # 4. Insert into database
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                INSERT INTO captures (capture_type, content, created_at)
                VALUES (?, ?, ?);
                """,
                (validated_type.value, trimmed, ts),
            )
            self._conn.commit()
            record_id = cursor.lastrowid
            return CaptureRecord(
                id=record_id,
                capture_type=validated_type,
                content=trimmed,
                created_at=ts,
            )
        except sqlite3.Error as exc:
            logger.error("Failed to save capture: %s", exc)
            raise StorageError(f"Database error while saving capture: {exc}") from exc

    def get_capture(self, capture_id: int) -> Optional[CaptureRecord]:
        """Retrieve a capture by primary key ID, or None if not found."""
        self._ensure_open()
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT id, capture_type, content, created_at
                FROM captures
                WHERE id = ?;
                """,
                (capture_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return CaptureRecord(
                id=row[0],
                capture_type=CaptureType(row[1]),
                content=row[2],
                created_at=row[3],
            )
        except sqlite3.Error as exc:
            logger.error("Failed to fetch capture %s: %s", capture_id, exc)
            raise StorageError(f"Database error while fetching capture {capture_id}: {exc}") from exc

    def list_recent(
        self,
        limit: int = 50,
        capture_type: Optional[Union[CaptureType, str]] = None,
    ) -> list[CaptureRecord]:
        """Retrieve the most recent captures in reverse-chronological order.

        Args:
            limit: Maximum number of captures to return (default 50).
            capture_type: Optional filter by CaptureType.

        Returns:
            List of CaptureRecord objects, newest first.
        """
        self._ensure_open()
        safe_limit = max(1, int(limit))

        try:
            cursor = self._conn.cursor()
            if capture_type is not None:
                validated_type = self._validate_capture_type(capture_type)
                cursor.execute(
                    """
                    SELECT id, capture_type, content, created_at
                    FROM captures
                    WHERE capture_type = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?;
                    """,
                    (validated_type.value, safe_limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT id, capture_type, content, created_at
                    FROM captures
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?;
                    """,
                    (safe_limit,),
                )

            rows = cursor.fetchall()
            return [
                CaptureRecord(
                    id=row[0],
                    capture_type=CaptureType(row[1]),
                    content=row[2],
                    created_at=row[3],
                )
                for row in rows
            ]
        except sqlite3.Error as exc:
            logger.error("Failed to list recent captures: %s", exc)
            raise StorageError(f"Database error while listing recent captures: {exc}") from exc

    def list_for_date_range(
        self,
        start_utc: str,
        end_utc: str,
    ) -> list[CaptureRecord]:
        """Retrieve captures created within a UTC date/time range.

        Args:
            start_utc: Inclusive lower bound ISO 8601 UTC timestamp string.
            end_utc: Inclusive upper bound ISO 8601 UTC timestamp string.

        Returns:
            List of CaptureRecord objects ordered chronologically (oldest to newest).
        """
        self._ensure_open()
        try:
            cursor = self._conn.cursor()
            cursor.execute(
                """
                SELECT id, capture_type, content, created_at
                FROM captures
                WHERE created_at >= ? AND created_at <= ?
                ORDER BY created_at ASC, id ASC;
                """,
                (start_utc.strip(), end_utc.strip()),
            )
            rows = cursor.fetchall()
            return [
                CaptureRecord(
                    id=row[0],
                    capture_type=CaptureType(row[1]),
                    content=row[2],
                    created_at=row[3],
                )
                for row in rows
            ]
        except sqlite3.Error as exc:
            logger.error("Failed to list captures for date range: %s", exc)
            raise StorageError(f"Database error while listing date range: {exc}") from exc

    def count(self) -> int:
        """Return the total number of stored capture entries."""
        self._ensure_open()
        try:
            cursor = self._conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM captures;")
            result = cursor.fetchone()
            return result[0] if result else 0
        except sqlite3.Error as exc:
            logger.error("Failed to count captures: %s", exc)
            raise StorageError(f"Database error while counting captures: {exc}") from exc

    def close(self) -> None:
        """Close the underlying SQLite connection safely (idempotent)."""
        if not self._is_closed:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass
            self._is_closed = True

    def __enter__(self) -> CaptureStore:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
