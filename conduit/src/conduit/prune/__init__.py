"""Package prune exports."""

from conduit.prune.grep_imports import SKIP_DIRS, prune_by_imports

__all__ = ["SKIP_DIRS", "prune_by_imports"]
