# Doodle — Decisions

**Status:** Draft for architecture review  
**Purpose:** Single source of truth for important product and technical decisions.

## Confirmed Product Decisions

### D-001 — Desktop first

**Decision:** Build Windows desktop first.

**Reason:** The desktop environment is the easiest place to establish the persistent companion interaction and gives Doodle access to useful future context signals.

**Status:** Confirmed.

---

### D-002 — Companion, not conventional reminder app

**Decision:** Doodle is a digital companion that can provide reminders, captures, and awareness features.

**Reason:** The persistent character and its behavior are the product identity. Reminders are capabilities, not the product itself.

**Status:** Confirmed.

---

### D-003 — Panda is the initial character

**Decision:** The first character will be a cute panda.

**Reason:** It is visually approachable and suitable for animation/content creation.

**Status:** Confirmed.

---

### D-004 — Quiet by default

**Decision:** Doodle should spend most of its time unobtrusively existing on the desktop.

**Reason:** Constant interruption would destroy the companion experience.

**Status:** Confirmed.

---

### D-005 — Character is draggable

**Decision:** Users can move Doodle to a preferred screen location, and the position should persist.

**Reason:** Different screen layouts and workflows have different safe areas.

**Status:** Confirmed.

---

### D-006 — Rule-based behavior before AI

**Decision:** Initial behavior will be deterministic/rule-based.

**Reason:** The core interaction should work without an LLM, and deterministic behavior is easier to debug and validate.

**Status:** Confirmed.

---

### D-007 — AI is a later layer

**Decision:** AI is not part of the initial desktop shell.

**Reason:** AI should augment a working companion rather than become a dependency before the product interaction is proven.

**Status:** Confirmed.

---

### D-008 — Event → state/context → decision → action → animation

**Decision:** This is the baseline behavior model for the MVP.

**Reason:** It provides a clean separation between sensing, decision-making, and presentation.

**Status:** Confirmed (Evolved in Architecture v2: see D-011 through D-015 and [docs/ARCHITECTURE_V2_COMPANION_CORE.md](file:///d:/PYTHON/doodle/doodle-desktop-companion/docs/ARCHITECTURE_V2_COMPANION_CORE.md)).

---

### D-009 — Modular architecture

**Decision:** Separate desktop/window, character/animation, events, behavior, persistence, AI, and integrations.

**Reason:** Doodle is expected to grow considerably, so these boundaries should exist early even though the first implementation remains small.

**Status:** Confirmed.

---

### D-010 — Local-first

**Decision:** The basic desktop companion should not require a cloud service.

**Reason:** Lower complexity, better reliability, and easier MVP development.

**Status:** Confirmed.

---

## Architecture v2 Approved Decisions (Companion Core)

Reference specification: [docs/ARCHITECTURE_V2_COMPANION_CORE.md](file:///d:/PYTHON/doodle/doodle-desktop-companion/docs/ARCHITECTURE_V2_COMPANION_CORE.md)

### D-011 — Activity as first-class domain concept

**Decision:** Establish `Activity` as a first-class domain concept distinct from animation frames, character state, or low-level UI widgets.

**Reason:** An activity represents what Doodle is doing over time (e.g., walking, resting, exploring) with its own lifecycle (start, tick, interrupt, finish) and goals, whereas an animation is merely a visual presentation technique.

**Status:** Approved architectural direction (Implementation pending).

---

### D-012 — CharacterState must not become universal cognitive state machine

**Decision:** Preserve `CharacterState` as a low-level physical posture/presentation state and forbid expanding it into a universal cognitive state machine.

**Reason:** Overloading `CharacterState` with moods, activities, thoughts, and complex behaviors creates combinatorial explosion and tight coupling across the entire codebase.

**Status:** Approved architectural direction (Implementation pending).

---

### D-013 — Decision layer separated from execution

**Decision:** The decision layer selects high-level companion Intent/Activity, while an independent Activity Execution layer coordinates physical realization (movement, animation selection, interruption, recovery).

**Reason:** Follows the central architectural principle: "Behavior should choose what Doodle wants to do, an Activity should describe what Doodle is doing, and the Character/Animation system should figure out how to physically perform it."

**Status:** Approved architectural direction (Implementation pending).

---

### D-014 — AI may influence semantic decisions but never directly control animation

**Decision:** Enforce a strict architectural boundary where AI policies may propose semantic intent, but must never directly manipulate animation frames, tick counters, or window pixel coordinates.

**Reason:** Ensures companion application stability, prevents frame stutter, decouples slow/probabilistic AI inference from 60 fps desktop rendering, and preserves deterministic offline resilience.

**Status:** Approved architectural direction (Implementation pending).

---

### D-015 — Companion Core precedes deeper context/integration work

**Decision:** Prioritize the Companion Core milestone (Activity model, execution boundary, movement primitives, and living behaviors) before deeper external integrations or complex context engines.

**Reason:** Without rich physical activities and robust execution boundaries, context signals have limited meaningful expressive outlets. Establishing the companion core first ensures subsequent context and utility integrations plug into a mature behavioral execution foundation.

**Status:** Approved architectural direction (Implementation pending).

---

## Approved Technical Decisions

### A-001 — PySide6 as desktop framework

**Decision:** Use Python + PySide6/Qt.

**Reason:** Already aligned with the project technology direction and sufficient for transparent desktop windows, animation, menus, timers, tray behavior, and Windows packaging.

**Status:** Approved.

---

### A-002 — Lightweight Qt/Python event mechanism

**Decision:** Use Qt signals and/or a very small internal event bus rather than an external event system.

**Reason:** The application is initially single-process and local. External messaging would be unnecessary complexity.

**Status:** Approved.

---

### A-003 — PNG frames / sprite-based animation abstraction

**Decision:** Treat animations as named frame sequences, rendered through Qt, rather than making GIF files the core animation abstraction.

**Reason:** Better control over timing, transitions, future effects, and asset organization. GIF can still be supported experimentally.

**Status:** Approved.

---

### A-004 — QSettings for lightweight preferences

**Decision:** Use QSettings for position and simple application preferences; reserve SQLite for structured user data such as journal/mood history.

**Reason:** Avoid using a database for settings that Qt already handles cleanly.

**Status:** Approved.

---

### A-005 — Windows-native APIs only behind adapters

**Decision:** When desktop context is introduced, isolate Windows-specific functionality behind adapter modules.

Examples:
- active window
- idle time
- foreground application
- fullscreen detection

**Reason:** Prevent OS-specific logic from leaking into the behavior engine.

**Status:** Approved.

---

### A-006 — No general screen understanding in early versions

**Decision:** Do not initially use OCR, computer vision, or an LLM to inspect arbitrary screen content.

**Reason:** Most useful early context can be obtained more reliably and cheaply from explicit signals such as active application, idle time, typing/activity, fullscreen state, and calendar state.

**Status:** Approved.

---

### A-007 — Single desktop process for MVP

**Decision:** Keep the MVP as one Python process with clear modules rather than splitting into services/processes.

**Reason:** Simplest reliable architecture for the current scope.

**Status:** Approved.

---

## Decisions Intentionally Deferred

These should not be decided until their phase is reached:

- Android/iOS implementation strategy.
- Browser-extension communication protocol.
- Calendar provider(s).
- Task/to-do providers.
- Cloud synchronization.
- Account system.
- AI model/provider.
- AI memory architecture.
- Character asset marketplace.
- Multi-character architecture beyond the current abstraction.
- Analytics/telemetry strategy.
- Monetization.
- Installer/update mechanism.
- Cross-platform support.

## Decision Rule

Before making a major architectural change:

1. State the problem.
2. Explain the proposed change.
3. Explain alternatives.
4. Explain tradeoffs.
5. Get approval when the change affects the established architecture.

Do not allow coding agents to independently redesign the architecture.
