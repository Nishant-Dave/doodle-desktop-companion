"""Deterministic mood foundation model for the Doodle companion.

Represents a small, strongly-typed mood vocabulary and managed transitions.
Mood is NOT character state; it influences behavior decisions without
replacing character animation state or UI interactions.
"""

from __future__ import annotations

import logging
import time
from enum import Enum
from typing import Callable, Optional, Union

logger = logging.getLogger(__name__)

# Centralized timing configuration defaults
DEFAULT_MOOD_DECAY_S: float = 60.0
DEFAULT_SLEEPY_THRESHOLD_S: float = 180.0


class Mood(str, Enum):
    """Vocabulary of supported companion mood values."""

    NEUTRAL = "NEUTRAL"
    HAPPY = "HAPPY"
    SLEEPY = "SLEEPY"
    CURIOUS = "CURIOUS"
    PLAYFUL = "PLAYFUL"

    def __str__(self) -> str:
        return self.value


class MoodManager:
    """Manages deterministic mood state, event-driven transitions, and decay.

    Follows:
        EVENT -> MOOD UPDATE -> BEHAVIOR DECISION
    """

    def __init__(
        self,
        initial_mood: Mood = Mood.NEUTRAL,
        decay_s: float = DEFAULT_MOOD_DECAY_S,
        sleepy_threshold_s: float = DEFAULT_SLEEPY_THRESHOLD_S,
        time_provider: Optional[Callable[[], float]] = None,
    ) -> None:
        self._current_mood: Mood = self._validate_mood(initial_mood)
        self._decay_s: float = max(0.0, float(decay_s))
        self._sleepy_threshold_s: float = max(0.0, float(sleepy_threshold_s))
        self._time_provider: Callable[[], float] = time_provider or time.monotonic
        self._last_mood_time: float = self._time_provider()

    @staticmethod
    def _validate_mood(value: Union[Mood, str]) -> Mood:
        """Validate and convert value into a valid Mood enum instance."""
        if isinstance(value, Mood):
            return value
        if isinstance(value, str):
            try:
                return Mood(value.upper().strip())
            except ValueError:
                raise ValueError(f"Invalid mood value: {value!r}. Must be one of {[m.value for m in Mood]}")
        raise TypeError(f"Mood must be a Mood enum or string, got {type(value).__name__}")

    @property
    def current_mood(self) -> Mood:
        """Return the current evaluated mood after applying deterministic decay."""
        now = self._time_provider()
        return self.get_mood(current_time=now)

    @property
    def raw_mood(self) -> Mood:
        """Return the stored mood without evaluating decay."""
        return self._current_mood

    @property
    def last_mood_time(self) -> float:
        """Return the timestamp when the mood was last set or updated."""
        return self._last_mood_time

    @property
    def decay_duration_s(self) -> float:
        """Return the duration in seconds before temporary moods decay toward NEUTRAL."""
        return self._decay_s

    @decay_duration_s.setter
    def decay_duration_s(self, value: float) -> None:
        self._decay_s = max(0.0, float(value))

    @property
    def sleepy_threshold_s(self) -> float:
        """Return the idle duration in seconds required to become eligible for SLEEPY."""
        return self._sleepy_threshold_s

    @sleepy_threshold_s.setter
    def sleepy_threshold_s(self, value: float) -> None:
        self._sleepy_threshold_s = max(0.0, float(value))

    @property
    def time_provider(self) -> Callable[[], float]:
        """Return the current time provider."""
        return self._time_provider

    @time_provider.setter
    def time_provider(self, provider: Callable[[], float]) -> None:
        self._time_provider = provider
        self._last_mood_time = self._time_provider()

    def set_mood(
        self,
        mood: Union[Mood, str],
        current_time: Optional[float] = None,
    ) -> Mood:
        """Explicitly set the companion mood and record update timestamp."""
        validated = self._validate_mood(mood)
        now = current_time if current_time is not None else self._time_provider()
        self._current_mood = validated
        self._last_mood_time = now
        logger.debug("Mood transitioned to %s at %s", self._current_mood, now)
        return self._current_mood

    def get_mood(
        self,
        current_time: Optional[float] = None,
        idle_duration_s: float = 0.0,
    ) -> Mood:
        """Evaluate deterministic decay and idle duration to return the active mood."""
        now = current_time if current_time is not None else self._time_provider()

        # 1. Decay temporary moods (HAPPY, PLAYFUL, CURIOUS) back toward NEUTRAL after inactivity
        if self._current_mood in (Mood.HAPPY, Mood.PLAYFUL, Mood.CURIOUS):
            elapsed_since_update = now - self._last_mood_time
            if elapsed_since_update >= self._decay_s:
                self._current_mood = Mood.NEUTRAL
                self._last_mood_time = now
                logger.debug("Temporary mood decayed to NEUTRAL at %s", now)

        # 2. Extended idle period gradually makes Doodle eligible for SLEEPY
        if self._current_mood == Mood.NEUTRAL and idle_duration_s >= self._sleepy_threshold_s:
            self._current_mood = Mood.SLEEPY
            self._last_mood_time = now
            logger.debug("Extended idle (%ss) transitioned mood to SLEEPY at %s", idle_duration_s, now)

        return self._current_mood

    def update_for_event(
        self,
        event: str,
        current_time: Optional[float] = None,
        idle_duration_s: float = 0.0,
        **kwargs,
    ) -> Mood:
        """Update mood deterministically in response to incoming events."""
        now = current_time if current_time is not None else self._time_provider()
        normalized_event = event.upper().strip()

        # 1. User click interaction: transitions to HAPPY
        if normalized_event == "CHARACTER_CLICKED":
            # If explicit mood override provided by context, honor it; otherwise HAPPY
            desired_mood = kwargs.get("mood", Mood.HAPPY)
            return self.set_mood(desired_mood, current_time=now)

        # 2. Drag interaction lifecycle: playful activity
        if normalized_event in ("DRAG_STARTED", "DRAGGING", "DRAG_RELEASED", "DRAG_FINISHED"):
            return self.set_mood(Mood.PLAYFUL, current_time=now)

        # 3. Proximity awareness: cursor nearby sparks curiosity
        if normalized_event == "CURSOR_ENTERED_PROXIMITY":
            return self.set_mood(Mood.CURIOUS, current_time=now)

        # 4. Extended idle or show/hide events: evaluate decay or sleepy threshold
        if normalized_event == "SHOW_REQUESTED":
            if self._current_mood == Mood.SLEEPY:
                return self.set_mood(Mood.NEUTRAL, current_time=now)

        return self.get_mood(current_time=now, idle_duration_s=idle_duration_s)

    def reset(self) -> None:
        """Reset mood back to default initial state (NEUTRAL)."""
        self._current_mood = Mood.NEUTRAL
        self._last_mood_time = self._time_provider()
