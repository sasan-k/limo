import subprocess
from pathlib import Path


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def make_git_repo(root: Path, name: str, files: dict[str, str]) -> str:
    """Create bare repo <root>/<name>.git whose branch main holds `files`; return its file:// URL."""
    src = root / f"{name}-src"
    src.mkdir(parents=True)
    for rel, text in files.items():
        (src / rel).parent.mkdir(parents=True, exist_ok=True)
        (src / rel).write_text(text)
    _git("init", "-b", "main", cwd=src)
    _git("add", ".", cwd=src)
    _git("-c", "user.name=limo", "-c", "user.email=limo@example.com", "commit", "-m", "init", cwd=src)
    bare = root / f"{name}.git"
    _git("clone", "--bare", str(src), str(bare), cwd=root)
    return bare.as_uri()


def make_empty_bare_repo(root: Path, name: str) -> str:
    """Create an empty bare repo <root>/<name>.git (no commits); return its file:// URL."""
    bare = root / f"{name}.git"
    _git("init", "--bare", str(bare), cwd=root)
    return bare.as_uri()
