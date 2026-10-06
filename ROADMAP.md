# Doodle — Roadmap

**Status:** Architecture v2 Milestone Evolution (Companion Core)  
**Baseline Date:** 2026-10-06  
**Reference Specification:** [docs/ARCHITECTURE_V2_COMPANION_CORE.md](file:///d:/PYTHON/doodle/doodle-desktop-companion/docs/ARCHITECTURE_V2_COMPANION_CORE.md)

---

## Historical Foundation Phases (Milestone 1 — Complete)

### Phase 0 — Product and Architecture Baseline
**Goal:** Establish one source of truth before coding.
- [x] Consolidate product vision.
- [x] Define desktop-first MVP.
- [x] Define explicit V1 exclusions.
- [x] Propose architecture boundaries.
- [x] Identify first implementation milestone.
- [x] Approve architecture decisions marked for review.
- [x] Create initial repository structure after approval.

### Phase 1 — Panda Desktop Shell
**Goal:** A stable Windows application with a living panda.
- [x] Python project skeleton.
- [x] PySide6 application startup.
- [x] Transparent frameless window.
- [x] Always-on-top behavior.
- [x] Panda asset rendering.
- [x] Basic animation controller.
- [x] Idle/sleep/sit/attention animations.
- [x] Dragging.
- [x] Position persistence.
- [x] System tray.
- [x] Clean startup/shutdown.

### Phase 2 — Character Interaction
**Goal:** Make Doodle feel interactive rather than decorative.
- [x] click/tap character
- [x] compact interaction menu
- [x] hover/click feedback where useful
- [x] basic character reactions
- [x] manual hide/show
- [x] configurable idle behavior
- [x] simple local settings

### Phase 3 — Quick Capture
**Goal:** In-place capture and lightweight journal timeline.
- [x] journal capture
- [x] mood capture
- [x] idea capture
- [x] quick “remember this” capture
- [x] timestamped local storage (SQLite CaptureStore)
- [x] simple day timeline & recent captures viewer

---

## Revised Milestone Structure (Architecture v2)

Following completion of the Foundation milestone and the Architecture v2 evaluation, the roadmap evolves to prioritize **Companion Core** before deeper context or external integrations:

```text
FOUNDATION (Complete)
      ↓
COMPANION CORE (Next Active Phase)
      ↓
CONTEXT
      ↓
COMPANION STATE
      ↓
MEMORY
      ↓
UTILITY
      ↓
AI COMPANION
      ↓
PRODUCTIZATION
```

### 1. FOUNDATION — COMPLETE
- Desktop shell (transparent, frameless window, system tray, drag mechanics)
- Character rendering & frame-based animation controller
- Interactive menu & click reactions
- Deterministic behavior engine & initial idle rotation
- Mood foundation (`Mood` enum & behavioral preference mapping)
- Quick Capture system (note/mood/idea input dialog & SQLite persistence)
- Capture timeline & recent captures viewer

### 2. COMPANION CORE — NEXT ACTIVE PHASE
- `Activity` first-class domain model & lifecycle definitions
- Decision layer refinement (candidate generation & intent selection)
- Activity execution boundary (`ActivityExecutor`)
- Animation/activity transitions & interruptibility foundation
- Movement & spatial relocation primitives (walking across screen bounds)
- Richer autonomous living behaviors (look around, yawn, curious, sit, sleep)
- Environmental interaction foundation (screen edge awareness)

#### Immediate Next Implementation Sequence (Planning Markers Only)
- **Task 21 — Activity domain model:** Base classes, lifecycle states, and protocol definitions.
- **Task 22 — Decision → Activity integration:** Behavior engine emits semantic activity candidates.
- **Task 23 — Activity execution boundary:** `ActivityExecutor` managing tick progression and callbacks.
- **Task 24 — Animation/activity transition foundation:** Smooth posture transitions and interrupt points.
- **Task 25 — Movement primitives:** Screen coordinate translation, velocity, and edge clamping.
- **Task 26 — Richer living behavior:** Assembled multi-phase activities.

*(Note: Tasks 21–26 are planning labels only; implementation has not begun.)*

### 3. CONTEXT
- Foreground application detection & classification
- User activity and idle time detection
- Fullscreen mode detection & autonomous behavior suppression
- Time of day & temporal rhythms
- Focus mode & quiet period management

### 4. COMPANION STATE
- Personality traits & baseline demeanor
- Needs modeling (rest, stimulation, socialization)
- Richer dynamic mood transitions
- Preference modeling & user affinity tracking
- Relationship continuity signals

### 5. MEMORY
- Explicit memories storage & retrieval
- Episodic interaction history
- User preference recall
- Longitudinal habit & pattern recognition
- Context-aware timeline integration

### 6. UTILITY
- Lightweight calendar awareness
- Task & reminder alerts through companion expressions
- Browser companion bridge
- Quick contextual actions

### 7. AI COMPANION
- Natural language companion conversation
- Journal summarization & empathetic reflection
- Cognitive reasoning for proactive suggestions
- Memory-augmented dialogue
- Adaptive personality expression

### 8. PRODUCTIZATION
- Customization options (colors, accessories, themes)
- Multi-character architecture (if justified by user demand)
- Windows installer & auto-updater
- Comprehensive onboarding & settings experience
- Optional end-to-end encrypted cloud sync

---

## Content Creation Track

Doodle should also be developed as a demonstrable build-in-public project.

Potential content themes:
- “I built a tiny panda that lives on my desktop.”
- “I made my panda learn when to stay quiet.”
- “My panda now knows when I'm in a meeting.”
- “I gave my panda a memory.”
- “I built a desktop companion from scratch with Python.”
- animation/behavior development clips
- before/after UX experiments

Content should document real product progress rather than drive architecture decisions.

---

## Current Next Step

Architecture v2 (Companion Core) specification is approved.

**Next Active Phase:** Companion Core (Tasks 21–26).  
Implementation will begin with Task 21 (Activity Domain Model) upon scheduling.

