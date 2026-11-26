import re

_ENTRY = re.compile(r"^- `([^`]+)`(?::(\d+)-(\d+))?")


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
        path, start, end = match.groups()
        result[path] = None if start is None or end is None else (int(start), int(end))
    return result
