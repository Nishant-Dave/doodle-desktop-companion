# Doodle — Architecture v2: Companion Core Specification

**Document Version:** 2.0.0  
**Phase:** Architecture v2 Design Checkpoint  
**Status:** Approved Architectural Direction (Design Baseline — Documentation Only)  
**Baseline Date:** 2026-10-06  
**Target Platform:** Windows desktop first (Python + PySide6)  

---

## Central Architectural Principle

> **"Behavior should choose what Doodle wants to do, an Activity should describe what Doodle is doing, and the Character/Animation system should figure out how to physically perform it."**

---

## 1. Status and Approval

- **Architecture Version:** v2 (Companion Core)
- **Status:** Approved Architectural Direction
- **Stage:** Design Checkpoint — **Documentation Only**
- **Implementation Status:** Implementation has **NOT** begun.

This specification establishes the formal architectural evolution for Doodle following a comprehensive re-evaluation of the current desktop prototype, desktop companion interaction patterns, and long-term product vision.

All architectural principles, domain abstractions, and boundaries detailed herein represent the **approved forward roadmap**. However, this document is strictly a design specification. No production Python source code, tests, dependencies, or asset hierarchies are modified by the adoption of this document. Existing modules continue to operate under Architecture v1 conventions until individual implementation tasks are scheduled and executed.

---

## 2. Why Architecture v2

### The Bottleneck of Architecture v1

In the original MVP architecture (v1), behavior and character presentation were coupled via a direct, linear pipeline:

```text
Event → BehaviorEngine → CharacterAction / CharacterState → AnimationController
```

While this was fundamentally sound for proving desktop viability, draggable transparent windows, simple idle cycles, and basic reactive animations, extending this model directly creates severe architectural friction:

1. **CharacterState Overload:** Every new high-level behavior (e.g., yawn, curious look, playing with a toy, reading, sleeping) threatens to demand a new global `CharacterState` enum value, turning a physical presentation state into an unmanageable cognitive state machine.
2. **Conflating Doing with Playing:** A direct path from decision to animation forces the decision engine to know about specific asset names, frame rates, and visual choreography.
3. **Inability to Support Long-Running Behaviors:** Autonomous desktop companions do not merely "fire an animation and forget." They engage in sustained activities composed of multiple phases: approach, loop, observe, react, recover.
4. **Missing Agency Layer:** As Doodle evolves toward a living, persistent presence, it requires internal drivers (mood, needs, personality, memory, context). Pushing these into a flat rule-to-animation mapping leads to combinatorial explosion in rule definitions.

### The Evolution: Desktop Pet to Persistent Companion

Doodle is evolving from a reactive desktop pet into a **persistent desktop companion**. To fulfill this vision, the system must gracefully accommodate:

- **Personality:** Stable baseline traits influencing demeanor, pace, and curiosity.
- **Mood:** Temporary affective states fluctuating with time, interactions, and environment.
- **Context:** Awareness of the user's focus, active applications, idle state, and quiet requirements.
- **Memory:** Historical awareness of user interactions, notes, capture moments, and shared routines.
- **Environmental Interaction:** Physical relationship with the screen, edges, corners, taskbar, and virtual objects.
- **Utility:** Non-intrusive awareness of schedule, reminders, notes, and productivity rhythms.
- **AI:** High-level semantic reasoning, natural conversation, and proactive reflection—without turning the companion into an unpredictable black box.

Architecture v2 introduces the structural boundaries necessary to support these capabilities without destabilizing the clean, lightweight foundation built in MVP.

---

## 3. Product and Architecture Insight

> **"Doodle is not fundamentally an animation player. It is an entity performing activities inside an environment."**

In simple desktop pet scripts, the character is treated as an animated sticker: an external timer ticks, chooses random frames, and blits them to a canvas.

In Doodle Architecture v2:
- The desktop is a **physical living environment** (with edges, surfaces, and active work contexts).
- Doodle is an **autonomous agent** with internal state that decides **what it intends to do**.
- What it does is formulated as an **Activity** (an ongoing process with purpose and lifecycle).
- The **Character and Animation** systems are the embodiment and physical apparatus that translate the activity into concrete movements, postures, and expressive frame sequences.

---

## 4. Current Architecture (As Built Today)

The current codebase represents a solid, functional MVP foundation. It is crucial to document what exists today without falsely claiming v2 is already implemented:

### Current Flow

```text
EVENT / CONTEXT → STATE / CONTEXT → DECISION → ACTION → ANIMATION
```

### Concrete Implementation Reality

1. **Event Dispatch:** High-level string events (`EVENT_IDLE_TIMEOUT`, `EVENT_CHARACTER_CLICKED`, `EVENT_CURSOR_ENTERED_PROXIMITY`, `EVENT_CONTEXT_CHANGED`, etc.) are processed by `BehaviorEngine` in [src/doodle/behavior/engine.py](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/behavior/engine.py).
2. **Rule-Based Decision:** `BehaviorEngine` evaluates `BehaviorContext` and runs deterministic rule checks in [src/doodle/behavior/rules.py](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/behavior/rules.py) (e.g., quiet periods, cooldowns, idle tiers, proximity rules).
3. **Action Output:** The rules yield a `BehaviorAction` (either `CHANGE_STATE` with a target `CharacterState`, `PLAY_ANIMATION` with an animation name, or `NOOP`).
4. **Direct Application:** `BehaviorEngine._apply_action()` directly instructs `Character`:
   - `character.set_state(action.state, loop=action.loop)`
   - or `character.play_animation(action.animation_name, loop=action.loop)`
5. **Character Presentation:** `Character` in [src/doodle/character/character.py](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/character/character.py) holds:
   - `CharacterState` enum (`IDLE`, `SIT`, `SLEEP`, `STRETCH`, `ATTENTION`)
   - `Mood` enum (`NEUTRAL`, `CURIOUS`, `PLAYFUL`, `HAPPY`, `SLEEPY`)
   - delegates frame rendering to `AnimationController` using frame PNG sequences in `assets/panda`.
6. **Desktop Shell:** `CompanionWindow` in [src/doodle/desktop/companion_window.py](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/desktop/companion_window.py) manages transparent, frameless rendering, dragging, screen clamping, and tray integration.
7. **Persistence:** `QSettings` stores window coordinates and basic settings; SQLite `CaptureStore` manages Quick Capture journal/idea/mood notes.
8. **Context Layer (Designed/In-Progress):** Normalized `DesktopContext` providing OS idle time, active window, fullscreen detection, and quiet suppression.

In the current code, **Activity does not yet exist**. Decisions directly dictate animation names or `CharacterState` transitions.

---

## 5. Target Architecture

### Target Conceptual Model

```text
EVENT / CONTEXT
       ↓
WORLD + COMPANION STATE
       ↓
    DECISION
       ↓
COMPANION INTENT
       ↓
    ACTIVITY
       ↓
   EXECUTION
       ↓
MOVEMENT + ANIMATION + UI
```

### Full Long-Term System Architecture

```text
                     USER / OS
                         ↓
                    PERCEPTION
                         ↓
                      CONTEXT
                         ↓
                 COMPANION STATE
     (mood / personality / needs / preferences)
                         ↓
                 DECISION / POLICY
                   ↙            ↘
        deterministic             AI
                   ↘            ↙
                        INTENT
                          ↓
                       ACTIVITY
                          ↓
                      EXECUTION
                       ↙      ↘
                movement      expression
                       ↘      ↙
                      CHARACTER
                          ↓
                    ANIMATION / UI

       +------------------------------------+
       |              MEMORY                |
       | (supporting subsystem informing    |
       |      Decision, Context, and AI)    |
       +------------------------------------+
```

### Information Flow Explanation

1. **Perception & Context:** Raw OS events (input ticks, foreground window changes, monitor topology, user interactions) are sensed, filtered, and normalized into immutable context snapshots.
2. **Companion State:** Doodle's internal affective and motivational state maintains internal continuity across ticks (how energetic, curious, or social Doodle feels).
3. **Decision & Policy:** The decision layer evaluates context against companion state and memory to form a high-level **Intent** (e.g., `Intent: TakeRest`, `Intent: GreetUser`, `Intent: Wander`).
4. **Activity:** The intent instantiates an **Activity**—a self-contained domain object describing the ongoing behavior, its prerequisites, phases, and termination conditions.
5. **Execution:** The execution layer coordinates the physical realization of the activity over time, managing movement trajectories, animation selection, micro-expressions, interruptions, and recovery.
6. **Character & Presentation:** The low-level character controller handles asset frame playback, spatial position updates, and desktop window composition.
7. **Memory Subsystem:** Operates alongside the main flow as a queryable store of past interactions, captured items, and derived habits.

---

## 6. Activity Model

### Activity as a First-Class Domain Concept

An **Activity** is an explicit, first-class domain abstraction representing a coherent unit of companion behavior over time.

An Activity is **not** an animation frame sequence, **not** a UI widget, and **not** a raw decision rule. It is an encapsulation of *what Doodle is actively doing*.

### Conceptual Activity Lifecycle

Every Activity exhibits a well-defined lifecycle managed by the execution layer:

```text
               [Instantiated]
                     ↓
                 can_start()? ── No ──→ [Rejected / Aborted]
                     ↓ Yes
                  on_start()
                     ↓
               ┌─→ on_tick(dt)
               │     ↓
               └── is_finished()?
                     ↓ Yes (or on_interrupt())
                  on_finish() / on_cleanup()
                     ↓
                  [Completed]
```

- **Prerequisites / Preconditions:** Validates that conditions allow the activity (e.g., not during drag, character has required space).
- **Execution Phases:** Many activities have internal stages (e.g., Anticipation → Main Action → Settle).
- **Tick / Progress:** Periodic evaluation for activities that evolve over multiple seconds (e.g., walking toward a screen edge).
- **Interruptibility:** Can be preempted by higher-priority events (e.g., user clicks character while it is sleeping) with clean cleanup.
- **Exit & Recovery:** Guarantees returning the character to a stable, neutral posture even if interrupted.

### Activity Examples

The following are conceptual examples illustrating the domain model, **not** an immediate implementation checklist:

- `Walk` — Relocating across the screen edge toward a target coordinate.
- `Sit` — Settling into a resting sitting posture.
- `Sleep` — Entering a prolonged dormant state with cyclic breathing/nap frames.
- `Stretch` — Brief restorative physical gesture.
- `LookAround` — Orienting attention across the desktop space.
- `Explore` — Patrolling or inspecting screen corners and borders.
- `Play` — Autonomous self-amusement or toy interaction.
- `WatchUser` — Tracking active typing or cursor proximity with curious glances.
- `React` — Immediate reactive response to click, drag, or sudden event.
- `ApproachObject` — Moving toward a desktop coordinate, boundary, or item.
- `Rest` — Low-energy presence during user focus periods.
- `Drink` / `Eat` — Autonomous sustenance role-play (e.g., munching bamboo).
- `Think` — Pondering animation during query processing or reflection.
- `Communicate` — Displaying a speech bubble, toast, or companion message.

### Why Activity Is Not an Animation

| Property | Animation | Activity |
| :--- | :--- | :--- |
| **Domain** | Presentation / Asset rendering | Companion behavior / Agency |
| **Duration** | Fixed frame count (e.g., 8 frames @ 10 fps) | Dynamic (seconds, minutes, or indefinite) |
| **Movement** | Static sprites in a bounding box | May translate window position across screen |
| **Interruption** | Usually plays to frame N or cuts abruptly | Coordinates graceful transition/recovery poses |
| **Composition**| Single sequence of PNG images | May sequence multiple animations (`start_walk` → `loop_walk` → `stop_walk`) |
| **Goals** | Pure visual fidelity | Fulfills an internal intent (rest, explore, entertain) |

---

## 7. Activity vs Character State

To prevent architectural degradation as Doodle expands, we establish hard conceptual boundaries:

```text
Mood        ≠  Activity
Personality ≠  Activity
Activity    ≠  Animation
Animation   ≠  Decision
```

### The Fallacy of the Universal Cognitive State Machine

A common failure mode in pet/companion architectures is expanding `CharacterState` into an all-encompassing enumeration:

```python
# ANTI-PATTERN: The universal cognitive state machine
class CharacterState(Enum):
    IDLE = 1
    WALKING = 2
    SLEEPING = 3
    CURIOUS = 4         # Conflates mood with physical state!
    HAPPY = 5           # Conflates affective emotion with state!
    TYPING_ALONG = 6    # Conflates activity with state!
    EATING_BAMBOO = 7   # Conflates activity with state!
    INTROVERTED = 8     # Conflates personality with state!
```

When `CharacterState` tries to model emotions, activities, personality traits, and physical poses simultaneously:
1. **Combinatorial Explosion:** What if the character is `HAPPY` while `WALKING`? Or `SLEEPY` while `SITTING`?
2. **Coupled Systems:** UI and animation logic must check dozens of state variations to decide how to draw a single frame.
3. **Rigid Transitions:** Every new activity requires editing global transition matrices across all character states.

### Architectural Rule

- **`CharacterState` remains physical and presentation-focused:** It represents low-level physical posture or presentation mode (e.g., `RESTING`, `POSTURED`, `MOVING`, `ATTENTIVE`), or serves as a simple rendering stance.
- **`Activity` represents ongoing behavior:** Doodle performs the `Explore` activity while in a happy `Mood` and playful `Personality` stance.
- **`CharacterState` must NEVER become a universal cognitive state machine.**

---

## 8. Decision Layer

### Evolution of Decision Making

The decision layer is the cognitive hub of Doodle. Its responsibility is to determine **what Doodle wants to do next** by selecting an Activity candidate.

```text
                      RULES / HEURISTICS
                              ↓
                     CANDIDATE ACTIVITIES
                              ↓
  CONTEXT + MOOD + PERSONALITY + NEEDS + PREFERENCES + MEMORY
                              ↓
                      SCORING / SELECTION
                              ↓
                       COMPANION INTENT
                              ↓
                           ACTIVITY
```

### Current vs Future Decision Flow

1. **Current (v1):**  
   Deterministic rules in `rules.py` receive events and check strict if/else conditions (e.g., `is_in_quiet_period`, cooldowns, idle tiers). If eligible, a single `BehaviorAction` is produced directly.
2. **Future (v2):**  
   - Multiple candidate activities are generated based on triggers (idle timeout, schedule, user action, internal need).
   - Candidate activities are filtered by context constraints (e.g., quiet mode prohibits loud or sudden activities).
   - Surviving candidates are evaluated/scored against current `CompanionState` (mood, personality traits, needs) and `Memory`.
   - The selected candidate is encapsulated as an `Intent` and handed to the execution layer.

### Deterministic Foundation First, AI Policy Later

The decision layer is designed with a dual-policy architecture:
- **Deterministic Policy (Primary & Default):** Fast, local, 100% predictable, offline, zero-latency rule/scoring engine.
- **AI Policy (Future Optional Enhancer):** Can suggest candidate intents or evaluate semantic priorities during conversational or reflective moments.

The execution and character systems do not care which policy produced the intent; they execute the resulting Activity uniformly.

---

## 9. AI Boundary

Architecture v2 establishes a strict, non-negotiable architectural boundary regarding Artificial Intelligence:

### The Non-Negotiable Boundary

> **AI must NEVER directly control animation frames or low-level window positioning.**

```text
ANTI-PATTERN (Forbidden):
AI (LLM / Model) ───[ Directly calls ]───→ play_frame(frame_3.png) / set_window_x(500)

CORRECT ARCHITECTURE:
AI ──→ Semantic Intent ──→ Activity ──→ ActivityExecutor ──→ Character / Animation
```

### Rationale

1. **Safety & Stability:** LLM outputs are probabilistic and occasionally malformed. If an AI output directly invokes graphics rendering or window movement, the companion application risks crashes, visual stutter, or erratic window behavior.
2. **Separation of Concerns:** High-level reasoning ("Doodle notices the user has been working for 2 hours and wants to suggest taking a break") is semantic. Rendering physical panda movement, selecting blinking frames, and handling screen edges is deterministic engineering.
3. **Latency Decoupling:** AI calls can take hundreds of milliseconds or seconds over network/local inference. The companion's desktop presence, breathing loops, and micro-reactions must maintain 60 fps responsiveness at all times without blocking on AI.
4. **Offline Resilience:** If AI is unavailable, disabled, or fails, the core companion remains 100% operational through deterministic policies.

---

## 10. Companion State

To prevent monolithic state coupling, internal companion characteristics are split into four distinct conceptual dimensions:

```text
                    COMPANION STATE
  ┌───────────────┬────────────────┬──────────────┬───────────────┐
  │     MOOD      │  PERSONALITY   │    NEEDS     │  PREFERENCES  │
  │  (Temporary)  │  (Persistent)  │  (Internal)  │ (Influencing) │
  └───────────────┴────────────────┴──────────────┴───────────────┘
```

### Definitions

1. **Mood (Temporary Affective State):**
   - Transient emotional tone fluctuating throughout the day (e.g., `CURIOUS`, `PLAYFUL`, `SLEEPY`, `NEUTRAL`, `FOCUSED`).
   - Influenced by recent interactions, time of day, active context, and activity history.
   - *Current Status:* An initial `Mood` enum exists in [src/doodle/character/mood.py](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/character/mood.py) and influences idle behavior tiers.
2. **Personality (Persistent Baseline Traits):**
   - Enduring companion traits that define baseline demeanor across days and weeks (e.g., calm vs. energetic, shy vs. bold, curious vs. laid-back).
   - Governs default activity probabilities, movement speeds, and reaction thresholds.
3. **Needs (Internal Motivations & Drivers):**
   - Internal biological/psychological drivers that accumulate over time (e.g., rest level, stimulation need, socialization need).
   - High needs naturally bias candidate activity selection (e.g., low energy elevates `Rest` and `Nap` activities).
4. **Preferences (Learned / Configured Affinities):**
   - Specific likes and dislikes (e.g., favorite desktop corner, preferred quiet hours, favorite idle toys).
   - Can be explicitly configured by the user or gently derived from interaction history.

### Design Constraint

**Do NOT define a detailed numerical personality/needs implementation yet.**  
Premature numeric simulation (e.g., Tamagotchi-style decay meters) adds complexity before core activity execution is proven. The conceptual separation exists now to ensure future state modeling fits cleanly into the decision pipeline.

---

## 11. Context

### Definition

**Context** represents normalized, structured information about the external environment: the user, the operating system, and the physical workspace.

```text
Sensors / OS Adapters ──→ Raw Signals ──→ Context Normalizer ──→ DesktopContext Snapshot
```

### Context Informs, But Does Not Decide

> **Context informs decisions. Context does not itself decide behavior.**

The context engine's sole responsibility is gathering and normalizing external reality into an immutable snapshot. It does not contain rules that dictate what the panda does.

### Potential Context Signals

- **Active Application:** Name/category of foreground app (e.g., IDE, terminal, browser, game, media player).
- **User Activity State:** Active input vs. idle (based on OS mouse/keyboard input timers).
- **Fullscreen Mode:** Whether a foreground app occupies the entire display (video, game, presentation).
- **Time of Day / Temporal Rhythms:** Local hour, work hours, late night, weekend.
- **Focus / DND Mode:** Active focus sessions, quiet periods, or system notifications status.
- **Meeting / Audio State:** Active microphone/camera use or calendar event.
- **Monitor & Display Geometry:** Virtual screen bounds, primary monitor, multi-display arrangements, scaling factors.

The behavior engine inspects `DesktopContext` when evaluating activity candidates (e.g., suppressing active gestures during fullscreen or late night).

---

## 12. Memory

### Distinguishing Capture Storage from Companion Memory

The project currently contains a SQLite-backed persistence layer in `src/doodle/persistence/capture_store.py`. It is critical to distinguish this from the future companion memory subsystem:

| Subsystem | Primary Owner | Purpose | Access Model |
| :--- | :--- | :--- | :--- |
| **Quick Capture Store** (Current) | User | User's explicit notes, journal thoughts, ideas, and captured moments. | User-driven capture UI, timeline viewing, local SQLite records. |
| **Companion Memory** (Future Architecture) | Companion | The companion's internal recall of past interactions, shared patterns, and user preferences. | Queried by Decision Layer and AI to contextualize behavior. |

### Future Companion Memory Categories

Companion memory will eventually encompass:

1. **Explicit Memory:** Facts and instructions explicitly shared by the user (e.g., "I usually have lunch at 1 PM").
2. **Episodic Memory:** Specific significant past events and interactions (e.g., "User clicked to comfort Doodle during a late-night work session yesterday").
3. **User & Companion Preferences:** Stable affinity models learned over time.
4. **Relationship & History:** Cumulative metrics of companionship (days active, interaction frequency, shared milestones).
5. **Derived Patterns:** Routine rhythms detected across sessions (e.g., "User tends to take breaks after 90 minutes of active coding").

### Design Constraint

**Do NOT design or implement semantic/vector memory yet.**  
Vector databases, embeddings, and complex retrieval pipelines are out of scope for the companion core foundation. Memory will be phased in when the companion core and context layers are mature.

---

## 13. Execution Layer

### Responsibilities of Activity Execution

The **Activity Execution Layer** is the operational bridge between high-level intent and low-level presentation. Once an Activity is selected by the decision layer, its executor coordinates its physical lifecycle.

```text
                     ACTIVITY EXECUTOR
                             │
     ┌───────────────┬───────┴───────┬───────────────┐
     ↓               ↓               ↓               ↓
  Movement       Animation      Interaction     Communication
 (Position /     (Clips /        (Click /         (Bubbles /
Trajectory)     Transitions)    Draggable)       Micro-toasts)
     │               │               │               │
     └───────────────┼───────────────┴───────────────┘
                     ↓
         Interruption / Completion / Recovery
```

### Execution Responsibilities

1. **Movement Coordination:** Translating abstract destination goals (e.g., "move to bottom-right corner") into smooth positional trajectories across desktop coordinates, clamping to safe screen boundaries.
2. **Animation Orchestration:** Selecting initial anticipation frames, looping core activity frames, and playing settling frames upon exit.
3. **Interaction Handling:** Maintaining awareness of user clicks or hover events while the activity is running.
4. **Communication:** Triggering speech bubbles, micro-toasts, or visual callouts if the activity includes messaging.
5. **Completion Handling:** Detecting natural activity termination, clearing temporary states, and reporting completion back to the behavior engine.
6. **Interruption Management:** If a high-priority event arrives (e.g., user drags Doodle or opens the menu), the executor cleanly interrupts the running activity without visual glitches.
7. **Recovery:** Ensuring the character gracefully returns to a neutral resting stance (`IDLE`) rather than freezing mid-frame.

---

## 14. Animation Evolution

### Frame-Based Animation Architecture Preserved

Doodle's frame-based animation system (Qt `QPixmap` sequences driven by `QTimer` inside `AnimationController`) has proven performant, lightweight, and completely reliable on Windows. Architecture v2 preserves this core rendering approach.

### Required Evolutionary Enhancements

As activities become more sophisticated, the animation system will require foundational capabilities:

- **Transitions:** Smooth interstitial frames or logical pathways between disparate poses (e.g., `sit` → `stand_up` → `walk` rather than popping directly from sitting to walking).
- **Interruptibility:** Defining "safe exit points" in looping animations so interruptions occur at cadence boundaries rather than creating visual frame snapping.
- **Directionality:** Supporting directional variants (facing left, right, looking up, looking down) through asset flipping or dedicated frame sequences.
- **Anticipation & Recovery:** Short preparatory cues before major movements and settling postures upon completion.
- **Completion Signaling:** Robust callbacks when single-shot animations finish, enabling seamless activity phase transitions.
- **Safe Fallback:** Guaranteed fallback to default idle frames whenever an optional animation asset is missing or corrupt.

### Explicit Constraint

> **Do NOT build a heavy, complex animation framework or skeletal 2D rigging system now.**  
The goal is lightweight transition and interruptibility support layered onto the existing `AnimationController`, not an elaborate game engine pipeline.

---

## 15. Environment and World Model

### The Desktop as a Living Space

In Architecture v2, the desktop is conceived as Doodle's physical living space. While not part of the immediate coding milestone, the architecture provides a mental model for environmental interaction:

```text
                           DESKTOP WORLD MODEL
   ┌─────────────────────────────────────────────────────────────┐
   │ Screen Corners (Resting Nooks)                              │
   │                                                             │
   │      Active Window Titlebar (Potential Perch)               │
   │      ┌─────────────────────────┐                            │
   │      │                         │                            │
   │      └─────────────────────────┘                            │
   │                                                             │
   │ Screen Edges / Taskbar Border (Walking / Wandering Track)   │
   │ Interactive Virtual Objects (Bamboo, Cushion, Toys)         │
   └─────────────────────────────────────────────────────────────┘
```

### Environmental Concepts (Future Architectural Direction)

- **Screens & Topology:** Awareness of virtual desktop bounds, primary and secondary displays, and monitor borders.
- **Edges & Borders:** Screen edges (especially above the Windows taskbar) serve as natural walking tracks and boundaries.
- **Corners:** Screen corners provide natural cozy spots for sleep and resting activities.
- **Window Boundaries (Future Exploration):** Interacting with active window borders (e.g., perching atop an inactive window).
- **World Elements / Objects:** Virtual items (e.g., a bamboo shoot, a cozy mat, a ball) that Doodle can approach, play with, or rest beside.

*Scope Clarification:* This represents future direction, **not** current implementation requirements. No physics engines or window-docking hooks should be built at this stage.

---

## 16. Architecture Boundaries

To ensure the codebase remains maintainable by a single developer and accessible to AI coding agents, subsystem boundaries are strictly defined:

```text
┌───────────────────────────────────────────────────────────────────────────┐
│                           ARCHITECTURE BOUNDARIES                         │
├─────────────────────┬─────────────────────────────────────────────────────┤
│ Subsystem           │ Core Responsibility                                 │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Desktop             │ Window creation, transparency, always-on-top,       │
│                     │ dragging, screen clamping, system tray.             │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Perception          │ Raw sensor adapters: OS input timers, foreground    │
│                     │ window hooks, monitor geometry.                     │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Context             │ Normalizes raw signals into immutable               │
│                     │ DesktopContext snapshots.                           │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Companion State     │ Tracks internal mood, personality traits, needs,    │
│                     │ and preferences across sessions.                    │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Decision            │ Evaluates context + state to select candidate       │
│                     │ activities; forms high-level Intent.                │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Activity            │ Encapsulates high-level behavior domain models,     │
│                     │ lifecycles, and parameters.                         │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Execution           │ Coordinates physical execution over time: movement, │
│                     │ animation selection, interruption, recovery.        │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Character           │ Represents physical entity; holds physical state;   │
│                     │ owns current visual frame and animation controller. │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Animation           │ Frame sequencing, timing loops, playback speed,     │
│                     │ transitions, and asset caching.                     │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ UI                  │ Interaction menu, Quick Capture dialog, settings,   │
│                     │ and speech bubbles.                                 │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Persistence         │ Lightweight local settings (QSettings) and user     │
│                     │ capture storage (SQLite CaptureStore).               │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ Memory              │ Long-term companion recall of episodic moments,     │
│                     │ interactions, and learned patterns.                 │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ AI                  │ High-level reasoning, conversation, and reflection; │
│                     │ interfaces ONLY via Semantic Intent.                │
├─────────────────────┼─────────────────────────────────────────────────────┤
│ External            │ Future adapters for calendar, tasks, browser        │
│ Integrations        │ extensions; normalizes data into Context.           │
└─────────────────────┴─────────────────────────────────────────────────────┘
```

---

## 17. Migration Strategy

### Incremental Evolution, NOT a Rewrite

We are **NOT** rewriting the existing project. The codebase has working, tested implementations for desktop windows, dragging, frame animations, interaction menus, Quick Capture, and deterministic behavior rules.

The migration from Architecture v1 to Architecture v2 will proceed **incrementally and non-destructively**:

```text
CURRENT PIPELINE (v1):
Event → BehaviorEngine → BehaviorAction → Character → AnimationController

MIGRATION BRIDGE (v1.5):
Event → BehaviorEngine ──→ [Translates to Activity] ──→ ActivityExecutor ──→ Character / Animation
                          (Legacy BehaviorAction path preserved as fallback)

TARGET PIPELINE (v2):
Context / Event → DecisionPolicy → Intent → Activity → ActivityExecutor → Character → AnimationController
```

### Migration Principles

1. **Zero Downtime for Existing Behaviors:** Existing idle rotations, drag reactions, click reactions, and quiet periods must remain fully functional throughout migration steps.
2. **No Mass Renaming:** Existing classes (`BehaviorEngine`, `Character`, `AnimationController`, `CompanionWindow`) remain in place. They will be evolved in-place through phased tasks.
3. **Additive Abstractions:** The `Activity` domain model and `ActivityExecutor` will be introduced alongside existing components, tested in isolation, and integrated step-by-step.
4. **Preserve Test Coverage:** Existing tests for behavior rules, character rendering, quick capture, and window positioning will remain green at each step.

---

## 18. What Stays Unchanged

Architecture v2 explicitly preserves the validated, reliable technological foundation of Doodle:

- **Language & Runtime:** Python 3.10+
- **GUI Framework:** PySide6 (Qt for Python)
- **Desktop Presentation:** Transparent, frameless, always-on-top floating window
- **Application Shell:** System tray lifecycle, single-instance management, clean shutdown
- **Window Mechanics:** Mouse-drag relocation, multi-monitor clamping, screen bounds checks
- **Event Plumbing:** Qt signals and slots for zero-latency, thread-safe intra-process messaging
- **Animation Technique:** High-performance PNG frame sequences driven by `QTimer` and `QPainter`
- **Character Abstraction:** `Character` managing embodiment; `AnimationController` managing frame ticks
- **Affective Baseline:** `Mood` system influencing behavioral tendencies
- **Interaction Feedback:** Proximity detection, click handling, and compact interaction menu
- **Decision Baseline:** Deterministic, local, zero-latency rule evaluation
- **Quick Capture Capability:** In-place capture dialog for journal thoughts, moods, and ideas
- **Persistence Mechanism:** `QSettings` for window preferences; local SQLite for capture data
- **OS Platform Isolation:** Windows native APIs isolated strictly behind adapter modules
- **Process Model:** Single-process, lightweight desktop application
- **Privacy Stance:** 100% local-first, zero telemetry, zero mandatory cloud dependencies

---

## 19. What Must NOT Happen (Anti-Patterns & Prohibitions)

To safeguard project simplicity and prevent scope explosion, the following are strictly prohibited:

1. **NO Giant State Machine:** Do not expand `CharacterState` to accommodate high-level behaviors, emotional states, or activities.
2. **NO AI Controlling Animation Frames:** AI must never dictate frame numbers, asset names, or window pixel coordinates.
3. **NO Animation-Specific Logic in Decision Rules:** Decision rules must select semantic activities, not frame counts or asset paths.
4. **NO Monolithic Context Engine:** Context must remain a set of focused, modular samplers yielding simple data objects.
5. **NO Premature Needs Simulation:** Do not build complex hunger/thirst/energy meters before basic activities execute smoothly.
6. **NO Semantic Memory / Vector Databases Now:** Do not add embeddings, ChromaDB, Pinecone, or LangChain at this stage.
7. **NO Complex Physics Engines:** Do not incorporate Box2D, Pygame physics, or rigid-body mechanics for desktop movement.
8. **NO Premature Plugin Architecture:** Do not build a plugin loading framework for speculative third-party extensions.
9. **NO Premature Multi-Character System:** Keep the core panda implementation rock-solid before abstracting character archetypes.
10. **NO Premature AI Integration:** Do not wire cloud LLM APIs into the main application loop before Companion Core is complete.
11. **NO Arbitrary Screen Understanding:** Do not implement OCR, computer vision, or background screen capture.

---

## 20. Revised Milestone Structure

Following this architecture review, the project milestone sequence is revised to place **Companion Core** immediately after the completed foundation:

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

### Detailed Milestone Breakdown

#### 1. FOUNDATION — COMPLETE
- Desktop shell (transparent, frameless window, system tray, drag mechanics)
- Character rendering & frame-based animation controller
- Interactive menu & click reactions
- Deterministic behavior engine & initial idle rotation
- Mood foundation (`Mood` enum & behavioral preference mapping)
- Quick Capture system (note/mood/idea input dialog & SQLite persistence)
- Capture timeline & recent captures viewer

#### 2. COMPANION CORE — NEXT ACTIVE PHASE
- `Activity` first-class domain model & lifecycle definitions
- Decision layer refinement (candidate generation & intent selection)
- Activity execution boundary (`ActivityExecutor`)
- Animation/activity transitions & interruptibility foundation
- Movement & spatial relocation primitives (walking across screen bounds)
- Richer autonomous living behaviors (look around, yawn, curious, sit, sleep)
- Environmental interaction foundation (screen edge awareness)

#### 3. CONTEXT
- Foreground application detection
- User activity & idle time sensing
- Fullscreen mode detection & autonomous behavior suppression
- Time of day & temporal rhythms
- Focus mode & quiet period management

#### 4. COMPANION STATE
- Personality trait representations & baseline inclinations
- Needs modeling (rest, stimulation, socialization drivers)
- Richer dynamic mood transitions
- Preference modeling & user affinity tracking
- Relationship continuity signals

#### 5. MEMORY
- Explicit memories storage & retrieval
- Episodic interaction memory
- User preference recall
- Longitudinal habit & pattern recognition
- Context-aware timeline integration

#### 6. UTILITY
- Lightweight calendar awareness
- Task & reminder alerts through companion expressions
- Browser companion bridge
- Quick contextual actions

#### 7. AI COMPANION
- Natural language companion dialogue
- Journal summarization & empathetic reflection
- Cognitive reasoning for proactive suggestions
- Memory-augmented conversation
- Adaptive companion personality expression

#### 8. PRODUCTIZATION
- Customization options (colors, accessories, themes)
- Multi-character architecture (if justified by user demand)
- Windows installer & auto-updater
- Comprehensive onboarding & settings experience
- Optional end-to-end encrypted cloud sync

---

## 21. Immediate Next Implementation Sequence

The next development phase implements the Companion Core milestone through focused, incremental tasks:

- **Task 21 — Activity Domain Model:**  
  Define the `Activity` base class, activity lifecycle hooks (`on_start`, `on_tick`, `on_interrupt`, `on_finish`), activity states, and core metadata contracts.
- **Task 22 — Decision → Activity Integration:**  
  Update `BehaviorEngine` candidate selection to emit high-level activity intents rather than raw animation names or state changes.
- **Task 23 — Activity Execution Boundary:**  
  Introduce `ActivityExecutor` to govern active activity execution, step progression, completion callbacks, and graceful interruption.
- **Task 24 — Animation / Activity Transition Foundation:**  
  Establish transition logic within `AnimationController` for smooth posture blending, safe interruption points, and fallback handling.
- **Task 25 — Movement Primitives:**  
  Implement spatial movement execution (smooth coordinate interpolation, screen edge clamping, velocity, direction orientation).
- **Task 26 — Richer Living Behavior:**  
  Assemble complete multi-phase activities (e.g., wander across taskbar, curious look, settled nap) utilizing the new activity and movement pipeline.

*(Note: These task titles are planning markers for roadmap sequencing. Implementation has not begun.)*

---

## 22. Architectural Quality Criteria

Future implementations under Architecture v2 must satisfy these quality criteria:

1. **Shared Primitives:** Doodle must be able to perform diverse activities (exploring, resting, reacting) composed from common movement and animation primitives.
2. **Decoupled Character States:** Adding a new companion activity must **never** require adding a new enum member to `CharacterState`.
3. **Clean Decision Boundary:** Decision and rule logic must evaluate semantic conditions and never manipulate animation frames, tick counters, or asset file paths.
4. **Pluggable AI Policy:** Future AI systems can propose candidate intents without bypassing or altering the execution or animation pipeline.
5. **Modular Context:** Context samplers must remain independent, testable components that do not coalesce into a monolithic engine.
6. **Decoupled Memory:** Memory expansion must operate through structured query interfaces without coupling persistence schemas to animation rendering.
7. **Independent Character Evolution:** Visual rendering and asset management must be freely improvable without altering decision rules.
8. **Preserved Stability:** All existing desktop features and test suites must remain stable and regression-free across migration steps.
9. **Single-Developer Comprehensibility:** The architecture must remain simple, transparent, and manageable by a single engineer without framework bloat.

---

## 23. Approval and Change-Control Rule

To prevent architectural drift and maintain technical coherence across development cycles, the project's change-control protocol is reaffirmed:

### Change-Control Protocol

Any major architectural modification requires an explicit five-step proposal:
1. **Problem Statement:** Detailed description of the concrete limitation or architectural defect.
2. **Proposed Change:** Precise specification of the proposed design alteration.
3. **Alternatives Considered:** Documented review of alternative designs.
4. **Tradeoffs:** Transparent analysis of added complexity, migration overhead, and performance impacts.
5. **Formal Approval:** Explicit human sign-off prior to implementing structural changes.

> **AI coding agents must NEVER independently redesign or refactor the system architecture.**
