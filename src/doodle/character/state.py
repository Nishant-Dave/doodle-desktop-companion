"""Character state definitions for Doodle."""

from enum import Enum


class CharacterState(str, Enum):
    """Vocabulary of supported character states."""

    IDLE = "IDLE"
    SIT = "SIT"
    SLEEP = "SLEEP"
    STRETCH = "STRETCH"
    ATTENTION = "ATTENTION"

    def __str__(self) -> str:
        return self.value
