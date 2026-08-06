"""Diff two export symbol sets."""

from __future__ import annotations


def diff_exports(
    old: set[str],
    new: set[str],
) -> tuple[set[str], set[str], dict[str, str]]:
    """
    Return (added, removed, renamed).
    Renames are heuristic: case-insensitive match or shared prefix/suffix.
    """
    added = set(new - old)
    removed = set(old - new)
    renamed: dict[str, str] = {}

    # Exact case-insensitive renames
    lower_new = {n.lower(): n for n in list(added)}
    for old_name in list(removed):
        match = lower_new.get(old_name.lower())
        if match and match != old_name:
            renamed[old_name] = match
            removed.discard(old_name)
            added.discard(match)

    # Shared stem heuristic (max_tokens -> max_completion_tokens already handled elsewhere;
    # here: FooBar -> FooBarV2, Client -> OpenAI)
    for old_name in list(removed):
        best: str | None = None
        for new_name in list(added):
            if old_name in new_name or new_name in old_name:
                best = new_name
                break
            if _token_overlap(old_name, new_name) >= 0.5:
                best = new_name
                break
        if best:
            renamed[old_name] = best
            removed.discard(old_name)
            added.discard(best)

    return added, removed, renamed


def _token_overlap(a: str, b: str) -> float:
    def tokens(s: str) -> set[str]:
        parts: list[str] = []
        cur = ""
        for ch in s:
            if ch.isupper() and cur:
                parts.append(cur.lower())
                cur = ch
            elif ch in {"_", "-"}:
                if cur:
                    parts.append(cur.lower())
                cur = ""
            else:
                cur += ch
        if cur:
            parts.append(cur.lower())
        return {p for p in parts if p}

    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)
