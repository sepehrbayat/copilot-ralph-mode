"""Allow running ralph_mode as ``python -m ralph_mode``."""

from .cli import main

raise SystemExit(main())
