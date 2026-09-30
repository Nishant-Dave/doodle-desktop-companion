"""Asset locating and loading for Doodle characters."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Union

from PySide6.QtGui import QPixmap

from doodle.character.state import CharacterState

# Default repository assets directory resolved relative to this module
DEFAULT_ASSETS_DIR: Path = Path(__file__).resolve().parents[3] / "assets"


def resolve_asset_path(
    character_name: str,
    state: Union[CharacterState, str],
    filename: Optional[str] = None,
    assets_dir: Optional[Path] = None,
) -> Path:
    """Resolve the filesystem path for a character state asset.

    Does not depend on the current working directory.
    """
    base_dir = Path(assets_dir) if assets_dir is not None else DEFAULT_ASSETS_DIR
    state_str = state.value if isinstance(state, CharacterState) else str(state)
    target_dir = base_dir / character_name.lower() / state_str.lower()

    if filename is not None:
        target_file = target_dir / filename
        if not target_file.is_file():
            raise FileNotFoundError(
                f"Asset file '{filename}' for character '{character_name}' in state '{state_str}' not found at {target_file}"
            )
        return target_file

    if not target_dir.is_dir():
        raise FileNotFoundError(
            f"Asset directory for character '{character_name}' in state '{state_str}' not found at {target_dir}"
        )

    candidates = sorted(target_dir.glob("*.png"))
    if not candidates:
        raise FileNotFoundError(
            f"No PNG asset found for character '{character_name}' in state '{state_str}' at {target_dir}"
        )

    return candidates[0]


def load_asset(
    character_name: str,
    state: Union[CharacterState, str],
    filename: Optional[str] = None,
    assets_dir: Optional[Path] = None,
) -> QPixmap:
    """Load a QPixmap asset for a given character and state.

    Raises FileNotFoundError if the directory or asset file does not exist.
    Raises ValueError if the image fails to load into a valid QPixmap.
    """
    asset_path = resolve_asset_path(
        character_name=character_name,
        state=state,
        filename=filename,
        assets_dir=assets_dir,
    )

    pixmap = QPixmap(str(asset_path))
    if pixmap.isNull():
        raise ValueError(f"Failed to decode image asset from {asset_path}")

    return pixmap


def load_animation_frames(
    character_name: str,
    animation_name: str,
    assets_dir: Optional[Path] = None,
) -> List[QPixmap]:
    """Load an ordered list of QPixmap frames for a character's named animation.

    Raises FileNotFoundError if the directory or frame assets do not exist.
    Raises ValueError if any frame image fails to decode.
    """
    base_dir = Path(assets_dir) if assets_dir is not None else DEFAULT_ASSETS_DIR
    target_dir = base_dir / character_name.lower() / animation_name.lower()

    if not target_dir.is_dir():
        raise FileNotFoundError(
            f"Animation directory for character '{character_name}' at {target_dir} not found"
        )

    frame_files = sorted(target_dir.glob("frame_*.png"))
    if not frame_files:
        frame_files = sorted(target_dir.glob("*.png"))

    if not frame_files:
        raise FileNotFoundError(
            f"No frame PNG assets found for character '{character_name}' animation '{animation_name}' at {target_dir}"
        )

    frames: List[QPixmap] = []
    for f in frame_files:
        pix = QPixmap(str(f))
        if pix.isNull():
            raise ValueError(f"Failed to decode frame from {f}")
        frames.append(pix)

    return frames
