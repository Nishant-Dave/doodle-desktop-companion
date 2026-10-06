# Doodle — Architecture

**Status:** Architecture v1 (Implemented Baseline) / Architecture v2 Approved (Companion Core)  
**Platform:** Windows desktop first  
**Implementation:** Python + PySide6  
**V2 Architecture Specification:** [docs/ARCHITECTURE_V2_COMPANION_CORE.md](file:///d:/PYTHON/doodle/doodle-desktop-companion/docs/ARCHITECTURE_V2_COMPANION_CORE.md)

## 1. Architectural Goal

Build a small, understandable desktop foundation that can later grow into a contextual companion without forcing the UI layer to know about every future feature.

The architecture should separate:

1. Desktop/window layer
2. Character/animation layer
3. Event system
4. Behavior/state engine
5. Mood/personality system
6. Persistent state
7. AI layer
8. External integrations

The first MVP only needs the first four in meaningful form, plus minimal persistence.

## 2. Proposed Technology Stack

### Core

- Python
- PySide6 / Qt
- Windows desktop APIs only where a native capability is genuinely required
- Local files/settings initially
- SQLite later for structured persistent event/journal data
- Git/GitHub for source control

### Avoid for now

- Web frontend frameworks
- Node.js backend
- Cloud database
- Docker
- Microservices
- Message brokers
- Redis
- External event infrastructure
- AI SDKs before AI is actually needed

## 3. High-Level Architecture

```text
                    Doodle Desktop Application
                              |
                +-------------+-------------+
                |                           |
        Desktop / Window Layer       Application Lifecycle
                |                           |
                +-------------+-------------+
                              |
                       Character Layer
                              |
                    Animation / Assets
                              |
                         Event Bus
                              |
                    Behavior Engine
                              |
             +----------------+----------------+
             |                                 |
       Context Signals                    User Actions
             |                                 |
             +----------------+----------------+
                              |
                         Decisions
                              |
                           Action
                              |
                       Panda Behavior
                              |
                         Animation
```

Future systems attach to the event/context side rather than directly manipulating the panda.

## 4. Suggested Module Boundaries

A proposed initial package structure:

```text
doodle/
├── app/
│   ├── application.py
│   └── lifecycle.py
│
├── desktop/
│   ├── companion_window.py
│   ├── tray.py
│   └── positioning.py
│
├── character/
│   ├── character.py
│   ├── animation.py
│   ├── state.py
│   └── assets.py
│
├── behavior/
│   ├── engine.py
│   ├── actions.py
│   └── rules.py
│
├── events/
│   ├── event.py
│   └── bus.py
│
├── persistence/
│   └── settings.py
│
├── ui/
│   └── interaction_menu.py
│
└── main.py
```

This is a starting boundary, not a commitment to create every file immediately.

## 5. Desktop / Window Layer

Responsibilities:

- create transparent top-level window
- frameless presentation
- always-on-top behavior
- drag/move behavior
- screen/desktop bounds
- show/hide
- close behavior
- tray integration
- later, optional context-aware positioning

The desktop layer should not decide why Doodle wants to move, sleep, remind, or interact.

## 6. Character Layer

Responsibilities:

- represent the panda
- expose character states
- play animations
- transition between animations
- accept behavior commands
- expose interaction signals

Example states:

```text
IDLE
SLEEPING
SITTING
STRETCHING
PLAYFUL
ATTENTION
THIRSTY
TIRED
```

Not all states need to exist in the first implementation.

The character layer should not contain calendar logic, screen-time logic, or journal logic.

## 7. Animation System

Recommended initial approach:

- individual PNG frames or sprite-sheet-derived frames
- QPixmap/QPainter or Qt-compatible rendering
- QTimer-driven animation
- named animations rather than hardcoded animation logic

Example conceptual API:

```text
play("idle")
play("sleep")
play("stretch")
play("attention")
```

The exact asset format and animation implementation should remain replaceable.

GIF can be used for experiments, but the architecture should not depend on GIF as the primary animation abstraction.

## 8. Event System

Use a lightweight in-process event model.

Examples:

```text
USER_CLICKED_CHARACTER
USER_DRAGGED_CHARACTER
IDLE_TIMEOUT
APP_STARTED
APP_EXITING
ANIMATION_FINISHED
REMINDER_TRIGGERED
CONTEXT_CHANGED
```

The event system should initially be simple Python/Qt signals or a small internal event bus.

Do not introduce an external messaging system.

## 9. Behavior Engine

Core future loop:

```text
EVENT
  ↓
STATE / CONTEXT
  ↓
DECISION
  ↓
ACTION
  ↓
ANIMATION
```

For MVP, decisions can be simple rule-based logic.

Example:

```text
IDLE_TIMEOUT
    ↓
behavior rule
    ↓
choose idle animation
    ↓
play animation
```

Later:

```text
ACTIVE_WINDOW_CHANGED
    ↓
context engine
    ↓
meeting/focus/movie/etc.
    ↓
behavior policy
    ↓
Doodle action
```

The behavior engine should be the main extension point for future intelligence.

## 10. Context Engine — Future Boundary

A future context layer can provide normalized signals such as:

```text
active_application = "VSCode"
is_typing = true
is_fullscreen = false
calendar_state = "meeting"
idle_seconds = 0
screen_session_minutes = 95
```

The behavior engine should consume these signals rather than directly calling Windows APIs or browser APIs.

This keeps platform-specific sensing separate from behavior decisions.

## 11. Persistence

### MVP

Use simple local settings storage for:

- character position
- visibility
- basic preferences
- selected character/asset set if applicable

Qt's QSettings is a reasonable candidate for this lightweight configuration.

### Later

Use SQLite for structured user data such as:

- journal entries
- mood events
- captured ideas
- behavioral history
- reminder history
- context events where persistence is actually useful

Do not introduce SQLite just to store a few window preferences.

## 12. Interaction Menu

The character should remain the primary interface.

Clicking the panda opens a compact menu.

Conceptual actions:

```text
Journal
Mood
Idea
Remember
Settings
```

The UI should be small and contextual.

The character should not open a large dashboard for every interaction.

## 13. External Integrations

Future integrations should sit outside the core character layer.

```text
Calendar Adapter
Task Adapter
Browser Adapter
Desktop Context Adapter
        |
        v
Normalized Context / Events
        |
        v
Behavior Engine
```

This prevents integrations from becoming tightly coupled to panda animations.

## 14. AI Layer

AI is intentionally separated from the MVP.

Future AI responsibilities could include:

- natural-language interaction
- summarizing captured moments
- finding patterns in journal/mood history
- suggesting reflections
- interpreting user-created notes
- personality adaptation

AI should not be required for basic companion behavior.

## 15. Error / Failure Philosophy

Doodle should fail quietly.

If a future integration fails:
- the panda should continue working
- the core desktop companion should remain usable
- integrations should degrade independently
- optional features should not crash the main application

## 16. Architectural Constraints

- No monolithic `main.py` containing all logic.
- No UI code deciding business behavior.
- No behavior rules directly coupled to OS-specific APIs.
- No future AI dependency in the core character system.
- No external service required for the basic desktop companion.
- No premature abstraction for hypothetical plugins.
- Prefer small modules with clear responsibilities.

## 17. First Implementation Boundary

The first implementation should stop at:

```text
Windows
  ↓
PySide6 application
  ↓
Transparent companion window
  ↓
Panda renderer
  ↓
Basic animation controller
  ↓
Drag + position persistence
  ↓
Click interaction
  ↓
Compact menu
  ↓
System tray
```

No context engine, AI, browser extension, calendar, journal database, or health logic should be added in this milestone.

## 18. Architectural Evolution — Architecture v2 (Companion Core)

Following the completion of the foundation milestone and an in-depth companion architecture review, the project has approved the Architecture v2 (Companion Core) evolution.

**Reference Specification:** [docs/ARCHITECTURE_V2_COMPANION_CORE.md](file:///d:/PYTHON/doodle/doodle-desktop-companion/docs/ARCHITECTURE_V2_COMPANION_CORE.md)  
**Status:** Approved Architectural Direction (Implementation pending).

### Central Principle

> **"Behavior should choose what Doodle wants to do, an Activity should describe what Doodle is doing, and the Character/Animation system should figure out how to physically perform it."**

### Core Model Evolution

- **Architecture v1 (Implemented Baseline):**  
  `EVENT → STATE/CONTEXT → DECISION → ACTION → ANIMATION`  
  Implemented as `Event → BehaviorEngine → BehaviorAction → Character → AnimationController`.
- **Architecture v2 (Approved Target):**  
  `EVENT / CONTEXT → WORLD + COMPANION STATE → DECISION → COMPANION INTENT → ACTIVITY → EXECUTION → MOVEMENT + ANIMATION + UI`

### Key Architectural Shifts

1. **Activity as a First-Class Concept (D-011):** Behaviors are encapsulated in an `Activity` domain model with lifecycle management (`on_start`, `on_tick`, `on_interrupt`, `on_finish`) rather than direct animation calls.
2. **Decoupled CharacterState (D-012):** `CharacterState` remains strictly physical/postural. It must never become a universal cognitive state machine.
3. **Execution Layer Boundary (D-013):** An independent `ActivityExecutor` coordinates spatial movement, animation clips, micro-expressions, interruptions, and safe recovery.
4. **Hard AI Boundary (D-014):** AI policies operate solely at the semantic decision level (intent proposal) and never directly control animation frames or window coordinates.
5. **Incremental Non-Destructive Migration:** Existing components (`BehaviorEngine`, `Character`, `AnimationController`, `CompanionWindow`) remain operational throughout migration, evolving via additive interfaces rather than rewrites.

