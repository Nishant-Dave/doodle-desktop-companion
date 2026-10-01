"""Thin entry point for the Doodle desktop application."""

from __future__ import annotations

import sys
from typing import Sequence

from doodle.app.application import DoodleApplication


def main(argv: Sequence[str] | None = None) -> int:
    """Instantiate and run the Doodle application."""
    app = DoodleApplication(argv, use_rich_idle=True)
    return app.run()



if __name__ == "__main__":
    sys.exit(main())
