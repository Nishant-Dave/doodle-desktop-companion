# Doodle — Project Specification

**Status:** Draft for architecture review  
**Baseline date:** 2026-09-30  
**Platform:** Windows desktop first  
**Product type:** Desktop digital companion

## 1. Product Vision

Doodle is a small, persistent digital companion that lives on the user's screen.

Most of the time Doodle should simply exist: sitting, sleeping, looking around, stretching, or doing small idle behaviors. When there is something useful to communicate, Doodle becomes expressive rather than behaving like a conventional notification panel.

The long-term product is not merely a desktop pet. It is a configurable companion layer that can combine:

- personality and visual expression
- contextual reminders
- quick journaling and moment capture
- mood logging
- screen-awareness
- calendar/task awareness
- behavioral adaptation
- eventually AI-powered reflection and interaction

The core product principle is:

> **Help the user stay aware while they are already spending time on a screen, without requiring them to open another app.**

A second principle is equally important:

> **Doodle should feel alive and intentional, not like a collection of random animations or nagging notifications.**

## 2. Product Problem

People spend large portions of their day on phones and computers, but self-awareness and healthy digital habits often require opening separate apps at the exact moment something happens.

Examples:

- A meaningful moment happens, but it is forgotten before nightly journaling.
- A user becomes frustrated but does not record the mood.
- A user works for a long period without taking a break.
- A user doom-scrolls for a long time without noticing.
- A task or calendar event is missed because it lives in another application.

Doodle reduces the friction between the moment and the action.

Example:

> Good news arrives → user notices Doodle → clicks it → selects “Add to journal” → writes a few words → continues.

The goal is not to make the user spend more time inside Doodle. The goal is to make Doodle useful while the user is doing other things.

## 3. Product Personality

Doodle should behave like a small companion rather than a notification system.

Normal state:
- quiet
- visually pleasant
- unobtrusive
- occasionally playful
- mostly idle

Attention state:
- expressive animation
- short contextual message
- minimal interruption
- clear action

Doodle should avoid:
- constant notifications
- guilt-heavy messaging
- repetitive nagging
- unnecessary UI
- interrupting active work, meetings, movies, or typing

## 4. Initial Character

The first character is a cute panda.

The character concept is inspired by the interaction model of older desktop assistants such as Clippy: a persistent character that occupies a small area of the screen, performs idle behaviors, reacts to interaction, and occasionally communicates.

This is inspiration for interaction behavior, not a requirement to reproduce Clippy's visual design.

Future characters may include other animals, plants, robots, ghosts, etc., but multiple characters are not part of the first MVP.

## 5. Desktop MVP

### MVP goal

Prove that a small animated companion can live comfortably on a Windows desktop and feel useful without becoming intrusive.

### MVP capabilities

1. Transparent floating desktop window.
2. Cute panda character rendered inside it.
3. Frameless presentation.
4. Always-on-top behavior.
5. Draggable character/window.
6. Remember the character's position between launches.
7. System tray/application lifecycle.
8. Basic idle animation/state system.
9. Several simple panda behaviors, for example:
   - idle
   - sit
   - sleep
   - stretch
   - look around
   - playful/random behavior
10. Click/tap interaction with the panda.
11. Small contextual interaction menu.
12. Basic local settings for behavior/visibility.
13. Clean exit/hide/show behavior.

### MVP interaction model

Clicking Doodle should expose a small set of actions without opening a large application window.

Initial menu can include placeholders or early implementations for:
- Journal
- Mood
- Idea
- Remember
- Settings

Only functionality that is actually implemented should be enabled. The first implementation milestone can initially use the interaction menu as a shell while the character/desktop behavior is validated.

## 6. V1 Product Direction After MVP

Once the companion foundation is validated, the next layer can introduce:

- quick journal capture
- mood capture
- idea/moment capture
- lightweight reminders
- configurable reminder rules
- screen/session awareness
- focus mode
- meeting/movie DND behavior
- calendar integration
- task/to-do integration
- browser extension
- richer character states
- self-awareness timeline
- weekly/monthly reflection
- optional AI-generated observations

The order should be driven by validated behavior rather than by trying to ship every idea at once.

## 7. Example Contextual Behaviors

These are product examples, not MVP requirements.

### Long work session

Doodle rubs its eyes.

> “My eyes are getting tired. How about a short break?”

### Late night

Doodle becomes sleepy.

> “Should we call it a day?”

### Long social-media session

Doodle reacts with tired/playful behavior.

> “We came here for five minutes, remember?”

### Upcoming meeting

Doodle points toward the reminder.

> “You have a meeting in 10 minutes.”

### Positive moment

Doodle offers:

> “Worth remembering?”

User can capture the moment.

## 8. Non-Goals / Explicit V1 Out of Scope

The following are deliberately excluded from the first desktop MVP:

- Mobile application.
- Android/iOS persistent overlay implementation.
- Browser extension.
- AI/LLM integration.
- Cloud backend.
- User accounts.
- Cloud synchronization.
- Social features.
- Marketplace.
- Payments/subscriptions.
- Advanced health tracking.
- Medical or health diagnosis.
- Wearable integration.
- Complex biometric tracking.
- OCR or general screen understanding.
- Computer vision-based interpretation of arbitrary screen content.
- Automatic analysis of every application the user opens.
- Full calendar/task integrations.
- Complex productivity scoring.
- Large analytics dashboard.
- Multi-character system.
- Character marketplace/custom asset editor.
- Voice interaction.
- Autonomous agent behavior.
- Cross-device synchronization.
- Production-grade installer/distribution pipeline.

These can be revisited after the core companion interaction is proven.

## 9. Success Criteria for the MVP

The MVP should answer:

1. Does Doodle feel pleasant to leave running?
2. Does the character feel alive rather than static?
3. Can the user move it easily?
4. Does it stay out of the user's way?
5. Is clicking it natural?
6. Can the application run for long periods without noticeable instability?
7. Can the architecture support future behavior/context modules without rewriting the desktop layer?

The first milestone is successful when the developer can leave Doodle running during normal computer use and genuinely want it to remain there.

## 10. Product Principles

- Build the smallest useful thing first.
- Prefer intentional behavior over random animation.
- Keep Doodle unobtrusive.
- Reduce friction rather than creating another destination app.
- Separate product decisions from implementation details.
- Avoid premature AI.
- Avoid premature integrations.
- Keep the architecture understandable.
- Make every future capability attachable without making the MVP complex.
- Optimize for a demonstrable product, not resume-driven technology choices.
