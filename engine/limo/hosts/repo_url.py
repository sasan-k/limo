import re

from limo.hosts.ports import HostError

_SEGMENT = r"[A-Za-z0-9_.\-]+"
_PATH = rf"{_SEGMENT}(?:/{_SEGMENT})+"
_PATTERNS = (
    re.compile(rf"^https://[^/\s]+/(?P<path>{_PATH})/?$"),
    re.compile(rf"^ssh://git@[^/\s]+/(?P<path>{_PATH})/?$"),
    re.compile(rf"^git@[^:/\s]+:(?P<path>{_PATH})/?$"),
)


def parse_repo(git_url: str) -> str:
    for pattern in _PATTERNS:
        match = pattern.match(git_url)
        if match:
            return re.sub(r"\.git$", "", match.group("path"))
    raise HostError("unsupported git url")
