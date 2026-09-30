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

**Decision:** This is the long-term behavior model.

**Reason:** It provides a clean separation between sensing, decision-making, and presentation.

**Status:** Confirmed.

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

## Proposed Technical Decisions Requiring Approval

### A-001 — PySide6 as desktop framework

**Proposal:** Use Python + PySide6/Qt.

**Reason:** Already aligned with the project technology direction and sufficient for transparent desktop windows, animation, menus, timers, tray behavior, and Windows packaging.

**Approval needed:** Yes.

---

### A-002 — Lightweight Qt/Python event mechanism

**Proposal:** Use Qt signals and/or a very small internal event bus rather than an external event system.

**Reason:** The application is initially single-process and local. External messaging would be unnecessary complexity.

**Approval needed:** Yes.

---

### A-003 — PNG frames / sprite-based animation abstraction

**Proposal:** Treat animations as named frame sequences, rendered through Qt, rather than making GIF files the core animation abstraction.

**Reason:** Better control over timing, transitions, future effects, and asset organization. GIF can still be supported experimentally.

**Approval needed:** Yes.

---

### A-004 — QSettings for lightweight preferences

**Proposal:** Use QSettings for position and simple application preferences; reserve SQLite for structured user data such as journal/mood history.

**Reason:** Avoid using a database for settings that Qt already handles cleanly.

**Approval needed:** Yes.

---

### A-005 — Windows-native APIs only behind adapters

**Proposal:** When desktop context is introduced, isolate Windows-specific functionality behind adapter modules.

Examples:
- active window
- idle time
- foreground application
- fullscreen detection

**Reason:** Prevent OS-specific logic from leaking into the behavior engine.

**Approval needed:** Yes.

---

### A-006 — No general screen understanding in early versions

**Proposal:** Do not initially use OCR, computer vision, or an LLM to inspect arbitrary screen content.

**Reason:** Most useful early context can be obtained more reliably and cheaply from explicit signals such as active application, idle time, typing/activity, fullscreen state, and calendar state.

**Approval needed:** Yes.

---

### A-007 — Single desktop process for MVP

**Proposal:** Keep the MVP as one Python process with clear modules rather than splitting into services/processes.

**Reason:** Simplest reliable architecture for the current scope.

**Approval needed:** Yes.

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
