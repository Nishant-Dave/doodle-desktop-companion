# Doodle — Roadmap

**Status:** Draft for architecture review

## Phase 0 — Product and Architecture Baseline

**Goal:** Establish one source of truth before coding.

- [x] Consolidate product vision.
- [x] Define desktop-first MVP.
- [x] Define explicit V1 exclusions.
- [x] Propose architecture boundaries.
- [x] Identify first implementation milestone.
- [ ] Approve architecture decisions marked for review.
- [ ] Create initial repository structure after approval.

## Phase 1 — Panda Desktop Shell

**Goal:** A stable Windows application with a living panda.

Deliverables:

1. Python project skeleton.
2. PySide6 application startup.
3. Transparent frameless window.
4. Always-on-top behavior.
5. Panda asset rendering.
6. Basic animation controller.
7. Idle/sleep/sit/attention animations.
8. Dragging.
9. Position persistence.
10. System tray.
11. Clean startup/shutdown.

**Validation:** Leave the panda running during normal desktop use for an extended session without the application becoming intrusive or unstable.

## Phase 2 — Character Interaction

**Goal:** Make Doodle feel interactive rather than decorative.

Deliverables:

- click/tap character
- compact interaction menu
- hover/click feedback where useful
- basic character reactions
- manual hide/show
- configurable idle behavior
- simple local settings

**Validation:** Interaction should feel natural and require very little effort.

## Phase 3 — Quick Capture

**Goal:** Test the strongest original product hypothesis.

Add:

- journal capture
- mood capture
- idea capture
- quick “remember this” capture
- timestamped local storage
- simple day timeline

**Validation:** Capture should take only a few seconds and should feel easier than opening a separate journal application.

## Phase 4 — Rule-Based Context

**Goal:** Make Doodle context-aware without AI.

Potential signals:

- active application
- idle time
- typing/activity
- fullscreen state
- time of day
- configurable focus periods

Potential behaviors:

- reduce interruptions while typing
- quiet mode during fullscreen
- focus mode
- break reminders
- bedtime behavior

**Validation:** Doodle should become more useful without becoming more annoying.

## Phase 5 — Calendar / Task Awareness

Add adapters for selected external systems.

Principle:

```text
External service
      ↓
Adapter
      ↓
Normalized event
      ↓
Behavior engine
```

No external service should become a core dependency.

## Phase 6 — Browser Companion

Build a browser extension only after the desktop behavior model is stable.

Potential capabilities:

- website/session awareness
- browsing-session duration
- social-media context
- browser-specific DND
- communication with desktop application

## Phase 7 — Self-Awareness Layer

Potential capabilities:

- mood timeline
- journal timeline
- screen-time patterns
- weekly reflection
- recurring pattern summaries
- user-controlled insights

## Phase 8 — AI Companion

Potential capabilities:

- natural-language conversation
- journal summarization
- reflection prompts
- personal pattern discovery
- adaptive personality
- context-aware suggestions

AI should augment the existing system rather than replace the deterministic behavior engine.

## Phase 9 — Distribution and Productization

Only after the core product proves useful:

- Windows installer
- update strategy
- crash reporting if needed
- onboarding
- settings UX
- asset/content pipeline
- optional accounts/cloud sync
- monetization experiments

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

## Current Next Step

Do not begin Phase 1 until the architecture review is approved.

After approval:

**First coding milestone = Panda Desktop Shell.**
