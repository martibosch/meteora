"""Helpers for optional dependencies."""

from collections.abc import Mapping
from types import ModuleType


def require_optional(
    deps: Mapping[str, ModuleType | None],
    *,
    extra: str,
    feature: str,
) -> None:
    """Raise if any optional dependency is missing."""
    missing = [name for name, module in deps.items() if module is None]
    if not missing:
        return
    dep_word = "dependency" if len(missing) == 1 else "dependencies"
    missing_list = ", ".join(missing)
    raise ImportError(
        f"{feature} requires optional {dep_word} {missing_list}. "
        f"Install with `pip install meteora[{extra}]`."
    )
