# Doodle — Panda Animation Asset Specification

**Status:** Approved Specification  
**Milestone:** Milestone 2 (Character Personality & Awareness) — Task 16  
**Character:** Panda  
**Target Platform:** Windows Desktop Companion (PySide6 / Qt)  
**Document Purpose:** Definitive asset design, technical specification, and generation guideline for upgrading Doodle's visual character from 2-frame prototype sprites to a continuous, living desktop companion.

---

## 1. Executive Summary & Objective

Manual testing across Milestones 1 and 2 established that while Doodle's underlying behavior engine, mood tracking, cursor proximity awareness, and physical interaction rules work reliably, the visual presentation feels robotic. The character currently resembles a disconnected collection of 2-frame sprite flips rather than a living creature inhabiting the user's desktop.

The primary bottleneck is not code architecture; it is **asset density, motion continuity, and visual grounding**.

This specification defines:
1. A factual audit of all existing assets and their visual limitations.
2. The core visual identity, canvas, and anchoring standards.
3. The definitive 8-animation Core Asset Pack (frame counts, timing, phases).
4. An actionable asset generation guideline for artists and AI image-generation pipelines.
5. Technical verification confirming that the existing PySide6 frame-based animation system can consume these upgraded assets with zero architectural redesign.

---

## 2. Factual Inventory of Current Assets

Every asset currently residing in `assets/panda/` was inspected on disk for resolution, format, alpha channel, bounding box, contact point, file size, SHA256 hash, and playback characteristics.

| Animation | Files | Dimensions | Format | Non-Zero Alpha Bounding Box | Contact Anchor $(X, Y)$ | Default Timing | Loop | Type | Key Observations |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`idle`** | 3 files: `frame_00.png`, `frame_01.png`, `panda_idle.png` | $256 \times 256$ | PNG (RGBA) | $X: 30..225$ ($W=196$), $Y: 30..246$ ($H=217$) | $(127, 246)$ | 3200ms quiet, 180ms blink | True | Ambient Idle | `panda_idle.png` is an identical byte-for-byte duplicate of `frame_00.png` (SHA: `2dc25785`). `frame_01.png` only closes eyelids (303 diff pixels, 0.5%). Zero chest expansion, breathing, or ear movement. |
| **`attention`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 32..223$ ($W=192$) to $X: 28..227$ ($W=200$), $Y: 26..246$ | $(127, 246)$ | 350ms / frame | True (Menu) | Interaction | Alert posture with raised ears. Jumps abruptly between pose A and pose B without head anticipation or settle. |
| **`curious`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 34..221$ ($W=188$) to $X: 36..219$ ($W=184$), $Y: 24..246$ | $(127, 246)$ | 350ms perk, 750ms tilt | False (Action) | Proximity / Idle | Expressive head tilt, but pops directly from center to tilt without eye lead-in, weight shift, or overshoot. |
| **`dizzy`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 22..233$ ($W=212$), $Y: 32..246$ | $(127, 246)$ | 300ms / frame | False (Action) | Drag Reaction | Swirly eyes and wobble. 2 frames alternate left-tilt and right-tilt like a metronome; lacks rotational motion. |
| **`playful`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 32..223$ ($W=192$) to $X: 22..233$ ($W=212$), $Y: 27..246$ | $(127, 246)$ | 280ms / frame | False (Action) | Autonomous Idle | Silhouette expands horizontally by 20px (8.5%) in a single frame step. Paws toggle up and down like cardboard cutouts. |
| **`recover`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 32..223$ ($W=192$) to $X: 30..225$ ($W=196$), $Y: 28..246$ | $(127, 246)$ | 450ms, 400ms | False (Action) | Transition | `frame_01.png` is identical to `idle/frame_00.png`. Acts as a settling bridge, but only 1 transitional frame (`frame_00`) exists before full rest. |
| **`sit`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 30..225$ ($W=196$), $Y: 30..246$ | $(127, 246)$ | 900ms / frame | True (State) | Character State | Paw position variation (3554 diff pixels, 5.4%). Very little visual differentiation from `idle`. |
| **`sleep`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 30..225$ ($W=196$), $Y: 30..246$ | $(127, 246)$ | 1200ms / frame | True (State) | Character State | Subtle breathing (968 diff pixels, 1.5%). Calming, but lacks ease-in/ease-out respiratory curves or gentle head droop. |
| **`stretch`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 30..225$ ($W=196$) to $X: 22..233$ ($W=212$), $Y: 30..246$ | $(127, 246)$ | 500ms enter, 850ms hold | False (Action) | Autonomous Idle | Paws jump from tucked sitting position directly to full wide stretch in 1 frame. No crouch anticipation or release ease. |
| **`surprised`** | 2 files: `frame_00.png`, `frame_01.png` | $256 \times 256$ | PNG (RGBA) | $X: 22..233$ ($W=212$), $Y: 22..246$ | $(127, 246)$ | 300ms / frame | True (Drag) | Physical Interaction | Held/dangling pose with wide eyes. Concept is strong, but 2 frames cause paws to snap back and forth while dragging. |

### Missing Conceptual Animations
The following behaviors are modeled in `IdleBehavior` or project specs but have **zero asset files** on disk:
- **`yawn`**: Missing completely. Behavior rules map `IdleBehavior.YAWN` to `"yawn"`, but availability checks correctly exclude it.
- **`look_around`**: Missing completely.
- **`blink`**: Missing as a standalone modular variation (only exists as `idle/frame_01.png`).
- **`wake_up`**: Missing completely.
- **`self_amusement`**: Missing completely.

---

## 3. Visual Diagnosis & Concrete Problems

Inspection of the frames and runtime playback identified four fundamental causes of robotic presentation:

### Problem 1: The 2-Frame Bottleneck (Frame Starvation)
Every existing animation contains exactly 2 frames. Physical motion cannot communicate weight, momentum, or anticipation with 2 frames. Any two-frame cycle alternates strictly as $A \leftrightarrow B$, which the human eye perceives as a blinking warning light or a cardboard cutout flipping back and forth.

### Problem 2: Instantaneous Pose Snapping (Missing In-Betweens)
In `stretch`, the panda transitions from width 196px to width 212px in a single frame. In `playful`, the arms pop up instantaneously. Real biological characters require:
- **Anticipation**: A subtle preparatory movement in the opposite direction (e.g., slight crouch down before stretching up).
- **In-betweens (Breakdowns)**: At least 1–2 transitional frames demonstrating continuous physical deformation.
- **Overshoot & Settle**: Moving slightly past the target pose before settling into it.

### Problem 3: Static Idle Presentation
In the base `idle/frame_00.png`, the panda's torso, ears, paws, and silhouette remain completely static for seconds at a time. The only variation in the raw assets is the eyelid closure in `frame_01.png`. Without subtle respiratory displacement (a 2–3 pixel rhythmic vertical chest lift) and micro-movements, the character appears frozen in ice between blinks.

### Problem 4: Silhouette Asymmetry and Grounding Stability
While all existing assets share the baseline ground contact point at $Y = 246$, horizontal silhouette shifts between frames are asymmetrical. In `playful`, frame 0 has bounding box $X \in [32, 223]$ while frame 1 expands to $X \in [22, 233]$. Because this expansion happens in one frame step, the panda visually "pops" horizontally, making the character feel unstable on the desktop surface.

---

## 4. Visual Style & Identity Specification

Doodle must possess a coherent, proprietary visual identity rather than looking like generic clipart.

### Character Proportions & Silhouette
- **Archetype**: Stylized, chubby baby panda cub sitting on its hindquarters.
- **Head-to-Body Ratio**: Approximately $1.0 : 1.1$ (large, expressive round head sitting directly on a soft, pear-shaped body without an elongated neck).
- **Silhouette**: Soft, rounded, and readable even at small desktop sizes ($128 \times 128$ to $160 \times 160$ pixels). Minimal tiny noisy details; strong outer contour.
- **Facial Features**:
  - Distinctive teardrop/oval black eye patches angled slightly outward at the top, conveying warmth and innocence.
  - Large dark pupils with clean specular highlights (giving a clear gaze direction toward the screen/user).
  - Small, rounded muzzle with a soft triangular black nose and a subtle gentle mouth line.
  - Rounded, hemispherical black ears positioned at the upper curve of the head.
- **Limbs**: Short, stubby black arms and rounded hind feet with light grey/pink paw pad accents visible when seated.

### Lighting, Shading & Palette
- **Palette**:
  - *Main Body Fur*: Warm soft off-white (`#F7F5F0` to `#FAF8F5`), avoiding harsh pure white (`#FFFFFF`) to prevent eye fatigue.
  - *Dark Fur (Ears, Patches, Limbs)*: Rich dark charcoal (`#1C1B20` to `#24232A`), avoiding pure digital black (`#000000`) so internal limb contours and folds remain readable.
  - *Accents*: Soft pastel peach/pink (`#F4C2B6`) for inner ear depth and paw pads.
- **Shading Style**: Clean 2D cel-shading with soft secondary ambient occlusion under the chin, arms, and belly.
- **Lighting Direction**: Gentle diffused lighting from the top-left ($10:30$ clock position). Lighting direction must remain strictly identical across every animation frame.

---

## 5. Canvas, Contact Anchor & Transparency Standards

To guarantee that frames can be played in sequence without visual jumping, floating, or jitter:

```text
+-------------------------------------------------------+ Y = 0
|                       256 px                          |
|                                                       |
|                                                       |
|                   [ Panda Head ]                      |
|                                                       |
|                  [ Panda Torso ]                      |
|                                                       |
|                 [ Seated Base ]                       |
|=======================================================| Y = 244 (Ground Baseline)
|                      12 px margin                     |
+-------------------------------------------------------+ Y = 255
                    X = 128 (Center Line)
```

1. **Resolution & Canvas**:
   - Every asset file MUST be exactly **$256 \times 256$ pixels**.
   - Standard desktop window displays Doodle scaled to $160 \times 160$ using Qt's `SmoothTransformation`. A $256 \times 256$ source asset guarantees crisp rendering on standard and High-DPI/4K displays without unnecessary GPU memory overhead.
2. **Contact Baseline (Grounding Anchor)**:
   - The bottom-most contact point of the panda's sitting base MUST be firmly anchored at **$Y = 244$** (12 pixels above the canvas bottom).
   - The horizontal center of mass MUST align with **$X = 128$**.
   - During seated animations (`idle`, `blink`, `look_around`, `curious`, `yawn`, `stretch`), the contact pixels at $Y = 244$ must NOT move up or down. The panda must feel physically anchored to the desktop surface.
   - The only exception is `surprised` (drag), where the panda is picked up into the air and its dangling feet sit at $Y = 225..235$.
3. **Transparency & Alpha Treatment**:
   - Format: 32-bit PNG (`RGBA8888`).
   - Background: Pure transparent (`Alpha = 0`).
   - Edges: Anti-aliased semi-transparent alpha fringes must blend cleanly to transparent. No black, white, or magenta matting halos around the fur perimeter.

---

## 6. The Core Animation Asset Pack

Rather than producing dozens of shallow clips, Doodle requires a focused pack of **8 cohesive animations** with intentional frame counts and physical phases:

```text
               +----------------------------------+
               |            IDLE LOOP             |
               | (Organic Breathing & Micro-Life) |
               +-----------------+----------------+
                                 |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
   [ LOOK_AROUND ]           [ CURIOUS ]             [ STRETCH / YAWN ]
(Environment Notice)     (Cursor Proximity)        (Fatigue / Relaxation)
         |                       |                       |
         +-----------------------+-----------------------+
                                 |
                                 v
                       +-------------------+
                       |  RECOVERY/SETTLE  |
                       +---------+---------+
                                 |
                                 v
                            [ IDLE REST ]
```

### Detailed Animation Specifications

#### 1. `idle` (Core Ambient Life)
- **Purpose**: Continuous resting presence on the desktop. Must communicate breathing and quiet vitality without distraction.
- **Phases**:
  - *Phase 1 (Inhale)*: Subtle 2–3px chest rise, ears angle upward by 1°, paws remain grounded ($800\text{ms}$).
  - *Phase 2 (Inhale Peak)*: Gentle expansion hold ($400\text{ms}$).
  - *Phase 3 (Exhale)*: Soft 2–3px chest descent back to base pose ($800\text{ms}$).
  - *Phase 4 (Rest Hold)*: Stillness at rest baseline ($1200\text{ms}$).
- **Recommended Frame Count**: 6 frames.
- **Timing**: $3200\text{ms}$ total cycle ($8$–$10$ FPS effective, variable duration).
- **Loop**: `True`.
- **Interruptible**: Yes, immediate.

#### 2. `blink` (Subtle Facial Micro-Action)
- **Purpose**: Independent facial variation to layer or intersperse with idle.
- **Phases**:
  - *Frame 1*: Eyelids half-closed ($60\text{ms}$).
  - *Frame 2*: Eyelids fully closed ($80\text{ms}$).
  - *Frame 3*: Eyelids opening with soft bounce ($60\text{ms}$).
- **Recommended Frame Count**: 3 frames.
- **Timing**: $200\text{ms}$ total.
- **Loop**: `False`.
- **Interruptible**: Yes.

#### 3. `look_around` (Environmental Awareness)
- **Purpose**: Autonomous idle behavior showing curiosity toward the desktop workspace.
- **Phases**:
  - *Anticipation*: Eyes dart slightly left, head prepares to turn ($150\text{ms}$).
  - *Action*: Head and torso smoothly swivel 15° to the left ($300\text{ms}$).
  - *Observation Hold*: Head held, eyes scan gently ($800\text{ms}$).
  - *Transition Across*: Head pans smoothly across center to the right ($400\text{ms}$).
  - *Observation Hold Right*: Brief gaze right ($600\text{ms}$).
  - *Recovery/Settle*: Head returns to center, soft nod into resting pose ($350\text{ms}$).
- **Recommended Frame Count**: 8 frames.
- **Timing**: $2600\text{ms}$ total.
- **Loop**: `False`.
- **Interruptible**: Yes, immediate.

#### 4. `curious` (Proximity Awareness Reaction)
- **Purpose**: Reaction when mouse cursor enters proximity zone. Communicates: *"Oh, what's over there?"*
- **Phases**:
  - *Anticipation/Perk*: Head lifts 4px, ears prick up forward, pupils widen ($200\text{ms}$).
  - *Head Tilt*: Head tilts 12° to the side, one ear swivels slightly forward ($350\text{ms}$).
  - *Curious Hold*: Gaze locks in tilt pose ($850\text{ms}$).
  - *Ease Out*: Head begins righting itself ($250\text{ms}$).
  - *Settle*: Head returns to neutral rest baseline with a gentle settling breath ($350\text{ms}$).
- **Recommended Frame Count**: 6 frames.
- **Timing**: $2000\text{ms}$ total.
- **Loop**: `False`.
- **Interruptible**: Yes, immediate.

#### 5. `yawn` (Sleepy / Long Idle Behavior)
- **Purpose**: Expressive deep relaxation indicating prolonged quiet or late hours.
- **Phases**:
  - *Anticipation*: Eyes squeeze shut, head tilts back slightly, chest expands ($400\text{ms}$).
  - *Deep Yawn Peak*: Mouth opens wide in cute rounded oval, eyes tightly squinted, shoulders rise ($900\text{ms}$).
  - *Release/Shudder*: Gentle vibration/shiver, mouth begins closing ($350\text{ms}$).
  - *Settle*: Mouth snaps softly shut, eyelids open drowsily, posture settles heavily back to resting baseline ($450\text{ms}$).
- **Recommended Frame Count**: 8 frames.
- **Timing**: $2100\text{ms}$ total.
- **Loop**: `False`.
- **Interruptible**: Yes, immediate.

#### 6. `stretch` (Post-Inactivity Awakening)
- **Purpose**: Waking up after sitting still; physical release of tension.
- **Phases**:
  - *Anticipation*: Paws pull inward, body compacts down 3px ($300\text{ms}$).
  - *Extension*: Paws reach outward and upward, body elongates vertically, head tilts up ($500\text{ms}$).
  - *Peak Hold*: Maximum extension held with trembling relaxation ($850\text{ms}$).
  - *Ease Out*: Arms drop down in a smooth arc toward body ($400\text{ms}$).
  - *Settle*: Paws touch ground, shoulders drop, body settles onto baseline ($450\text{ms}$).
- **Recommended Frame Count**: 8 frames.
- **Timing**: $2500\text{ms}$ total.
- **Loop**: `False`.
- **Interruptible**: Yes, immediate.

#### 7. `dizzy` (Post-Drag Physical Reaction)
- **Purpose**: Reaction when released after user drags Doodle across the screen.
- **Phases**:
  - *Wobble Left*: Head rolls left, eyes spiral into spirals, ears flop opposite ($200\text{ms}$).
  - *Wobble Right*: Head rolls right, body sways ($200\text{ms}$).
  - *Wobble Center/Lag*: Staggered compensation sway ($200\text{ms}$).
  - *Looping Cycle*: 4 alternating wobble frames forming a continuous circular gyroscopic motion ($800\text{ms}$).
- **Recommended Frame Count**: 4 frames (looping wobble cycle) + transition to `recover`.
- **Timing**: $800\text{ms}$ per wobble cycle; plays 1–2 cycles.
- **Loop**: `False` (finishes and triggers `recover`).
- **Interruptible**: Yes, immediate.

#### 8. `recover` (Universal Settle & Re-grounding Bridge)
- **Purpose**: Crucial transitional bridge that takes the character from any intense reaction (`dizzy`, interrupted actions) smoothly back to resting `idle`.
- **Phases**:
  - *Head Shake*: Quick sharp head shake to clear eyes ($150\text{ms}$).
  - *Dazed Settle*: Blink eyes open, shoulders drop back to normal posture ($300\text{ms}$).
  - *Baseline Match*: Exact pose, scale, and contour matching `idle` frame 0 ($350\text{ms}$).
- **Recommended Frame Count**: 4 frames.
- **Timing**: $800\text{ms}$ total.
- **Loop**: `False`.
- **Interruptible**: Yes, immediate.

---

## 7. Master Summary: Recommended Asset Specifications

| Animation Name | Directory | Target Frame Count | Recommended FPS / Frame Durations | Looping | Settle Destination |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`idle`** | `assets/panda/idle/` | 6 frames | $8\text{ FPS}$ ($400\text{ms}$, $400\text{ms}$, $400\text{ms}$, $400\text{ms}$, $800\text{ms}$, $800\text{ms}$) | `True` | Continuous Loop |
| **`blink`** | `assets/panda/blink/` | 3 frames | $15\text{ FPS}$ ($60\text{ms}$, $80\text{ms}$, $60\text{ms}$) | `False` | `idle` Frame 0 |
| **`look_around`** | `assets/panda/look_around/` | 8 frames | $10\text{ FPS}$ ($150$, $300$, $800$, $200$, $200$, $600$, $200$, $150\text{ms}$) | `False` | `idle` Frame 0 |
| **`curious`** | `assets/panda/curious/` | 6 frames | $10\text{ FPS}$ ($200$, $350$, $850$, $250$, $200$, $150\text{ms}$) | `False` | `idle` Frame 0 |
| **`yawn`** | `assets/panda/yawn/` | 8 frames | $8\text{ FPS}$ ($200$, $200$, $450$, $450$, $200$, $150$, $250$, $200\text{ms}$) | `False` | `idle` Frame 0 |
| **`stretch`** | `assets/panda/stretch/` | 8 frames | $8\text{ FPS}$ ($300$, $250$, $250$, $850$, $250$, $200$, $250$, $150\text{ms}$) | `False` | `idle` Frame 0 |
| **`dizzy`** | `assets/panda/dizzy/` | 4 frames | $12\text{ FPS}$ ($150$, $150$, $150$, $150\text{ms}$) | `False` | `recover` Frame 0 |
| **`recover`** | `assets/panda/recover/` | 4 frames | $10\text{ FPS}$ ($150$, $150$, $250$, $250\text{ms}$) | `False` | `idle` Frame 0 |

---

## 8. Directory & File Naming Conventions

All assets conform to the project's zero-dependency loader in [`load_animation_frames`](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/character/assets.py#L77):
- Directories MUST be lowercase: `assets/panda/<animation_name>/`.
- Frames MUST be zero-padded sequential PNGs: `frame_00.png`, `frame_01.png`, `frame_02.png`, etc.
- Remove redundant standalone files (e.g., `panda_idle.png` in `idle/`).

```text
assets/
└── panda/
    ├── idle/
    │   ├── frame_00.png
    │   ├── frame_01.png
    │   ├── frame_02.png
    │   ├── frame_03.png
    │   ├── frame_04.png
    │   └── frame_05.png
    ├── blink/
    │   ├── frame_00.png
    │   ├── frame_01.png
    │   └── frame_02.png
    ├── look_around/
    │   ├── frame_00.png
    │   └── ... (frame_07.png)
    ├── curious/
    │   ├── frame_00.png
    │   └── ... (frame_05.png)
    ├── yawn/
    │   ├── frame_00.png
    │   └── ... (frame_07.png)
    ├── stretch/
    │   ├── frame_00.png
    │   └── ... (frame_07.png)
    ├── dizzy/
    │   ├── frame_00.png
    │   └── ... (frame_03.png)
    └── recover/
        ├── frame_00.png
        └── ... (frame_03.png)
```

---

## 9. Asset Generation Specification (AI / Illustrator Pipeline)

To ensure that future frame generation yields **one continuous character** rather than disparate illustrations:

### Master Reference Image (The Visual Anchor)
All prompt workflows must condition on `assets/panda/idle/frame_00.png` as the single canonical source of truth for:
- Exact fur color values (off-white `#F7F5F0`, dark charcoal `#1C1B20`).
- Proportions (head diameter = 180px, sitting base width = 196px).
- Eye patch geometry and ear placement.

### ControlNet / Pose Constraints
- Use an **open-pose or depth control grid** anchored to $X=128, Y=244$.
- The ground contact plane at $Y=244$ must be locked with a 100% rigid weight mask for all seated poses.
- Only articulated joints (ears, eyelids, mouth, head angle, paw elevation) may vary between frames.

### Canonical Prompt Structure
When using image generation models:
```text
Positive Prompt:
chibi baby panda desktop companion, seated pose, cute, clean vector illustration style,
cel shaded, soft ambient studio lighting from top-left, warm off-white and rich charcoal fur,
perfectly transparent background, isolated sprite, centered on 256x256 canvas, anchored contact base,
consistent character sheet, [FRAME_SPECIFIC_ACTION]

Negative Prompt:
photorealistic, noisy fur texture, human hands, background scenery, ground shadows,
rectangular borders, white outline, halo, cut off limbs, deformed ears, extra paws,
inconsistent lighting, dramatic angle, perspective distortion
```

---

## 10. Technical Evaluation of Existing Architecture

**Question:** Can Doodle's existing codebase support this improved asset pack without an architectural overhaul?

### Verdict: YES.
The existing architecture is **100% sufficient** and requires no framework changes:
1. **Asset Loading**: [`load_animation_frames`](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/character/assets.py#L77) automatically globs `frame_*.png` and sorts them alphabetically. It natively handles any frame count (from 2 frames up to 20+ frames) without code modification.
2. **Animation Model**: [`Animation`](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/character/animation.py#L154) already supports variable frame counts, arbitrary frame durations via `frame_durations_ms`, and looping overrides via `loop_frame_count`.
3. **Playback & Rendering**: [`AnimationController`](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/character/animation.py#L196) dynamically updates its `QTimer` interval on every frame tick (`advance_frame`), maintaining deterministic timing without timer accumulation or listener leakage.
4. **Behavior Engine & Rules**: The behavior pipeline `EVENT -> MOOD/RULES -> ACTION -> CHARACTER -> ANIMATION CONTROLLER` cleanly separates decision-making from presentation. When new animation folders (`yawn`, `look_around`) are added to disk, [`is_behavior_available`](file:///d:/PYTHON/doodle/doodle-desktop-companion/src/doodle/behavior/rules.py#L131) will immediately detect them and incorporate them into idle selection policies automatically.

**Conclusion:** No new rendering engines, blend tree systems, physics libraries, or skeletal frameworks are required. Upgrading the PNG files according to this specification will immediately produce the desired fluid, living desktop companion.
