import re

# `path`, `path:10-20`, `path`:10-20, and several ranges `path:10-20,30-40` (inside or after the backticks)
_ENTRY = re.compile(r"^- `([^`:]+)(?::([\d,\- ]+))?`(?::([\d,\- ]+))?")
_RANGE = re.compile(r"(\d+)-(\d+)")


def _span(ranges: str | None) -> tuple[int, int] | None:
    """Several ranges read as one span, from the first start to the last end."""
    pairs = [(int(a), int(b)) for a, b in _RANGE.findall(ranges or "")]
    if not pairs:
        return None
    return min(a for a, _ in pairs), max(b for _, b in pairs)


def parse_context_pack(plan_text: str) -> dict[str, tuple[int, int] | None]:
    """Map each path in the plan's `## Context pack` section to its line range, or None for the whole file."""
    result: dict[str, tuple[int, int] | None] = {}
    in_section = False
    for line in plan_text.splitlines():
        if line == "## Context pack":
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        match = _ENTRY.match(line)
        if match is None:
            continue
        path, inside, after = match.groups()
        result[path] = _span(inside or after)
    return result
