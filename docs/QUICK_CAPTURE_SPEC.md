# Doodle — Quick Capture Storage & UX Specification

**Document Version:** 1.0.0  
**Phase:** Phase 3 — Quick Capture (Foundation Design)  
**Status:** Approved Architecture Design  
**Baseline Date:** 2026-10-03  
**Target Platform:** Windows desktop first  

---

## 1. Product Goal

Quick Capture is Doodle's lightweight, zero-friction desktop capture mechanism. It validates one of Doodle's core founding hypotheses:

> **Help the user stay aware while they are already spending time on a screen, without requiring them to open another application.**

### The Experience

```text
Doodle
  ↓
Quick interaction (click character / select capture action)
  ↓
Compact capture card appears
  ↓
Choose capture type & enter short text
  ↓
Save locally
  ↓
Card dismisses & Doodle returns to quiet life
  ↓
Continue working
```

### Core Design Principles

1. **Sub-5-second interaction:** Capturing a thought, journal entry, mood, or memory anchor must be faster and lighter than opening an external application (e.g., Obsidian, Notion, Apple Notes, browser tabs).
2. **Non-destination companion:** Doodle is an unobtrusive desktop presence, not a heavy document management suite or project management tool.
3. **Calm return to quiet:** Saving or cancelling a capture immediately returns Doodle to its peaceful resting rhythm without modal interruptions, notifications, or nag dialogues.

---

## 2. Capture Types

The initial conceptual capture vocabulary is strictly limited to four small, intentional types:

| Capture Type | Purpose | Example Input |
| :--- | :--- | :--- |
| `IDEA` | Sudden insights, technical ideas, creative thoughts. | *"Use SQLite user_version pragma for schema migrations."* |
| `JOURNAL` | Quick reflection on what just happened or a personal milestone. | *"Wrapped up Milestone 2 animations, feeling great."* |
| `MOOD` | Snapshot of emotional state or energy level. | *"Focused and energized after a short walk."* |
| `REMEMBER` | Short memory anchors to revisit later. | *"Check on Sarah's PR review before 4 PM."* |

### Scope Safeguard
No additional types are permitted in this phase. Specifically excluded:
- Tasks / to-do items with checkboxes
- Reminders with alarm times
- Calendar events / scheduling
- Projects / milestones
- Contacts / people
- File attachments / images / audio

---

## 3. Minimal Data Model

The data model is deliberately minimal, storing only what is genuinely required to record the capture and later display it in a timeline.

### Conceptual Fields

| Field | Type | Required | Description |
| :--- | :--- | :--- | :--- |
| `id` | Integer (Primary Key) | Yes | Unique, auto-incrementing sequential identifier. |
| `capture_type` | String Enum | Yes | One of `IDEA`, `JOURNAL`, `MOOD`, `REMEMBER`. |
| `content` | String (Text) | Yes | User's entered text (trimmed, non-empty). |
| `created_at` | String (ISO 8601 UTC) | Yes | Timezone-aware creation timestamp in UTC with `Z` suffix. |

### Field Exclusion Analysis

- **Why no `updated_at`?** Quick Captures are immutable snapshots of a specific moment. Editing introduces versioning and sync complexity unnecessary for a companion capture anchor.
- **Why no `tags` or `categories`?** Capture types already provide primary categorization. Tagging adds input friction and breaks the sub-5-second capture goal.
- **Why no `companion_mood` or `window_position`?** The capture is user data, not companion telemetry. Decoupling user content from internal companion state keeps the schema clean and durable.

---

## 4. Storage Decision

### Evaluation of Options

1. **Qt `QSettings` (INI / Registry):**
   - *Strengths:* Already in use for `window/position`.
   - *Weaknesses:* Designed for key-value configuration. Lacks query indexing, date-range filtering, and ACID transaction safety. Unbounded text entries in INI files risk corruption.
   - *Verdict:* **Rejected for user captures.** Reserved exclusively for application settings per Decision `A-004`.

2. **Flat JSON / JSONL Files:**
   - *Strengths:* Human-readable.
   - *Weaknesses:* Requires rewriting the entire file or parsing the entire log into memory. No indexed lookups for date ranges. Concurrency and crash resilience require manual locking.
   - *Verdict:* **Rejected.**

3. **Embedded SQLite (`sqlite3`):**
   - *Strengths:* Included in the Python standard library with zero external dependencies. ACID compliant and crash-resilient. Extremely fast single-file storage. Supports native indexed queries (`ORDER BY created_at DESC`) and date range filters (`WHERE created_at BETWEEN ? AND ?`) directly supporting Phase 3 day timeline views and Phase 7 history views.
   - *Architecture Alignment:* Pre-authorized in `ARCHITECTURE.md` (Sections 2 & 11) and `DECISIONS.md` (Decision `A-004`).
   - *Verdict:* **Selected.**

### Storage Architecture Rules

- Use Python's built-in `sqlite3` module directly.
- **Do NOT** implement a generic repository framework.
- **Do NOT** introduce an ORM abstraction (e.g., SQLAlchemy, Peewee).
- Parameterized SQL queries only (no string formatting/concatenation).

---

## 5. Proposed Database Schema

```sql
-- Schema version tracking
PRAGMA user_version = 1;

-- Core captures table
CREATE TABLE IF NOT EXISTS captures (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_type TEXT NOT NULL CHECK(capture_type IN ('IDEA', 'JOURNAL', 'MOOD', 'REMEMBER')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Chronological index for timeline and reverse-chronological history lookups
CREATE INDEX IF NOT EXISTS idx_captures_created_at 
ON captures (created_at DESC);

-- Composite index for filtering by capture type chronologically
CREATE INDEX IF NOT EXISTS idx_captures_type_created 
ON captures (capture_type, created_at DESC);
```

### Schema Properties

1. **Enforced Constraints:** The `CHECK(capture_type IN (...))` constraint guarantees data integrity at the database engine level.
2. **Fast Reverse-Chronological Lookups:** The `idx_captures_created_at` index delivers $O(\log N)$ performance for recent captures and timeline queries.
3. **Zero Migration Overhead for Phase 3 Timeline:** A query like `SELECT * FROM captures WHERE created_at >= ? AND created_at < ? ORDER BY created_at ASC` executes with maximum efficiency without requiring schema revisions.

---

## 6. Persistence Module Responsibility

### Package Structure

The persistence layer lives cleanly in `src/doodle/persistence/`:

```text
src/doodle/persistence/
├── __init__.py           # Exports SettingsManager and CaptureStore
├── settings.py           # Existing QSettings manager for window position & prefs
└── capture_store.py      # New SQLite store for user captures (Phase 3)
```

### Architectural Separation

```text
+-------------------------------------------------------+
|                       UI Layer                        |
|   (CompanionWindow, InteractionMenu, QuickCaptureCard) |
+-------------------------------------------------------+
                           │ Emits capture signals
                           ▼
+-------------------------------------------------------+
|                   Application Layer                   |
|                  (DoodleApplication)                  |
+-------------------------------------------------------+
                           │ Invokes storage methods
                           ▼
+-------------------------------------------------------+
|                   Persistence Layer                   |
|        SettingsManager         CaptureStore           |
|          (QSettings)             (SQLite)             |
+-------------------------------------------------------+
```

### Module Boundaries

- `CaptureStore` has **zero PySide6/Qt dependencies**. It operates purely with standard library types (`str`, `int`, `datetime`, `dataclass`, `sqlite3`, `pathlib`).
- `CaptureStore` handles connection lifecycle, table creation, record mapping, parameterized queries, and clean closing.
- Default database file location on Windows:
  `%APPDATA%/Doodle/doodle_captures.db` (aligned with `SettingsManager` location).
- Supports an explicit file path parameter or `":memory:"` to enable fully isolated, fast, non-flaky automated unit testing.

### Proposed Python Interface

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

class CaptureType(str, Enum):
    IDEA = "IDEA"
    JOURNAL = "JOURNAL"
    MOOD = "MOOD"
    REMEMBER = "REMEMBER"

@dataclass(frozen=True)
class CaptureRecord:
    id: Optional[int]
    capture_type: CaptureType
    content: str
    created_at: str

class CaptureStore:
    def __init__(self, db_path: Optional[str] = None) -> None: ...
    def save_capture(self, capture_type: CaptureType, content: str, created_at: Optional[str] = None) -> CaptureRecord: ...
    def get_capture(self, capture_id: int) -> Optional[CaptureRecord]: ...
    def list_recent(self, limit: int = 50, capture_type: Optional[CaptureType] = None) -> list[CaptureRecord]: ...
    def list_for_date_range(self, start_utc: str, end_utc: str) -> list[CaptureRecord]: ...
    def count(self) -> int: ...
    def close(self) -> None: ...
```

---

## 7. Quick Capture UI Interaction Flow

### Entry Points

1. **Companion Menu Action:**
   - User clicks Doodle $\to$ character enters `ATTENTION` $\to$ `InteractionMenu` appears.
   - User clicks one of the active capture items (`Journal`, `Mood`, `Idea`, `Remember`).
   - The menu dismisses and the compact `QuickCaptureCard` immediately appears near the companion window.
2. **Keyboard Shortcut (Future Phase):**
   - Global hotkey (e.g. `Ctrl+Shift+D`) can directly open the capture card without opening the menu.

### Interaction Sequence

```text
User clicks "Idea" in menu
           ↓
Menu closes; QuickCaptureCard opens anchored near Doodle
           ↓
Card displays:
  - Type selector pill (pre-selected to "Idea")
  - Clean text input field (auto-focused with cursor active)
  - Micro-action hint ("Enter to save  ·  Esc to dismiss")
           ↓
User types thought: "Implement SQLite capture store"
           ↓
[Press Enter] ──────────────────────────→ [Press Esc / Click outside]
      ↓                                                ↓
Record saved to SQLite                           Operation cancelled
      ↓                                                ↓
Doodle displays brief acknowledgment             Capture card dismisses
      ↓                                                ↓
Capture card dismisses                           Doodle returns to calm IDLE
      ↓
Doodle returns to calm IDLE
```

### UI Characteristics

- **Compact Dimensions:** Approximately 220px wide $\times$ 110px high.
- **Anchoring:** Positioned deterministically relative to the companion window using existing `compute_menu_position()` logic.
- **Keyboard-First:** Auto-focuses text input on open; `Enter` saves; `Esc` cancels.
- **Consistent Styling:** Translucent dark card aesthetic matching `InteractionMenu` (`menuCard` styling).

---

## 8. Event Model

Only three specific events are required to coordinate Quick Capture across components:

| Event Name | Source | Handler | Purpose |
| :--- | :--- | :--- | :--- |
| `EVENT_CAPTURE_REQUESTED` | `InteractionMenu` / Hotkey | `DoodleApplication` | Opens `QuickCaptureCard` initialized with the requested `CaptureType`. |
| `EVENT_CAPTURE_SAVED` | `QuickCaptureCard` | `DoodleApplication` $\to$ `CaptureStore`, `BehaviorEngine` | Persists the record to SQLite and initiates a brief positive acknowledgment reaction on Doodle. |
| `EVENT_CAPTURE_CANCELLED` | `QuickCaptureCard` | `DoodleApplication` $\to$ `BehaviorEngine` | Closes the card without saving; returns Doodle cleanly to `IDLE` state. |

### Event Rules

- No unneeded CRUD events (`CAPTURE_EDITED`, `CAPTURE_DELETED`, `CAPTURE_SYNCED`, `CAPTURE_TAGGED`).
- Events flow through existing PySide6 signals/slots without introducing an external event broker.

---

## 9. Timestamp Approach

### Standard: UTC ISO 8601 Strings

All timestamps are generated and stored as UTC strings formatted to the millisecond with a literal `Z` timezone indicator:

```text
YYYY-MM-DDTHH:MM:SS.ffffffZ
Example: 2026-10-03T16:45:12.384910Z
```

### Why This Format?

1. **Lexicographical Sort Equivalence:** ISO 8601 strings in UTC sort alphabetically in the exact same order as chronologically. In SQLite, `ORDER BY created_at DESC` functions correctly without datetime parsing overhead.
2. **Timezone Independence:** Storing in UTC prevents daylight saving shifts, travel between timezones, or local system clock timezone changes from corrupting chronological sequence.
3. **Native Python Compatibility:** Parses cleanly with standard library `datetime.fromisoformat()` in Python 3.11+.
4. **Separation of Storage and Presentation:** The database stores UTC. When the timeline is rendered in future milestones, the UI converts UTC to the user's active local display format (`dt.astimezone().strftime(...)`).

---

## 10. Error Handling & Failure Philosophy

Following Doodle's architectural principle: **"Doodle fails quietly."**

### Database Failure Protections

1. **Crash / Corruption Resilience:**
   - SQLite handles process termination mid-write via atomic write-ahead logging/journaling.
   - If a database file cannot be opened due to disk corruption:
     - Log error via Python `logging`.
     - Rename damaged file to `doodle_captures.db.corrupt.<timestamp>`.
     - Reinitialize a clean schema so the user never encounters a hard crash.
2. **Graceful Save Failures:**
   - If saving fails (e.g. disk full), `save_capture` logs the error and raises a specific `StorageError` or returns `None`.
   - The UI does **not** discard user input silently; it keeps the text intact in the card and displays a subtle retry indicator.
3. **Data Validation:**
   - Strips leading/trailing whitespace.
   - Rejects empty strings (saving blank captures is disallowed).
   - Enforces a generous practical character limit (e.g., 10,000 characters) to prevent runaway memory allocation.

---

## 11. Testing Strategy

When implementation begins, tests should be organized into:

### 1. Pure Store Unit Tests (`tests/test_capture_store.py`)

- **In-memory SQLite (`:memory:`):**
  - Table initialization and schema creation.
  - Creating and saving `CaptureRecord` for each `CaptureType`.
  - Reading a capture by `id`.
  - Rejection of invalid capture types (raises `ValueError`).
  - Rejection of empty or whitespace-only content.
  - Correct UTC ISO 8601 timestamp generation.
  - Sorting verification: `list_recent()` returns records strictly in descending chronological order.
  - Filtering verification: `list_recent(capture_type=CaptureType.IDEA)` returns only ideas.
  - Date range filtering verification: `list_for_date_range()` returns records strictly within bounds.

### 2. On-Disk Persistence Tests (`tests/test_capture_persistence.py`)

- **File-backed SQLite with temporary directory:**
  - Create `CaptureStore` on temporary disk file.
  - Save records across multiple capture types.
  - Close the store connection.
  - Instantiate a new `CaptureStore` pointing to the same file.
  - Verify all records, IDs, and timestamps persist accurately across simulated application restart.

### 3. Application & UI Integration Tests (`tests/test_quick_capture_integration.py`)

- Click interaction menu $\to$ `EVENT_CAPTURE_REQUESTED` emitted.
- Submitting text $\to$ `EVENT_CAPTURE_SAVED` $\to$ record appears in `CaptureStore`.
- Cancelling $\to$ `EVENT_CAPTURE_CANCELLED` $\to$ zero records written, companion returns to `IDLE`.
- Companion behavior: saving a capture initiates an interaction quiet period.

---

## 12. Future Extension Boundaries

This foundation supports future roadmap phases without redesigning the core schema:

```text
Phase 3 (Quick Capture)    ──→ captures table (id, type, content, created_at)
                                      │
Phase 3 (Day Timeline)     ──→ SELECT * FROM captures WHERE created_at >= ?
                                      │
Phase 4 (Context Rules)    ──→ ALTER TABLE captures ADD COLUMN context_app TEXT;
                               (or optional capture_context metadata table)
                                      │
Phase 7 (Self-Awareness)   ──→ Read-only aggregate queries on captures table
                                      │
Phase 8 (AI Reflection)    ──→ Read-only text analysis of captures table
```

---

## 13. Explicit Non-Goals (Scope Restrictions)

The following are strictly out of scope for Milestone 3 Task 18A:

- **No full Quick Capture UI implementation** in this design task.
- **No Timeline UI / history viewer.**
- **No AI / LLM features:** No summarization, categorization, auto-tagging, embeddings, or vector search.
- **No Cloud Services:** No cloud sync, remote databases, user accounts, or cross-device messaging.
- **No Productivity Bloat:** No tasks, due dates, checkboxes, calendar sync, project boards, or notifications.
- **No Media Attachments:** No images, audio clips, speech-to-text, or OCR.
- **No Architecture Changes:** No changes to animation, behavior engine, mood, or cursor proximity systems.

---

## 14. Summary

The Quick Capture foundation uses Python's standard-library `sqlite3` to store immutable, timestamped user thoughts across four simple capture types (`IDEA`, `JOURNAL`, `MOOD`, `REMEMBER`). It preserves the existing separation of concerns, adds zero third-party dependencies, keeps Doodle quiet and responsive, and naturally scales into future timeline and reflection features.
