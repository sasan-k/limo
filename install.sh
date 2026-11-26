#!/usr/bin/env bash
# Links the factory into ~/.claude so skills are available in every project.
#   ~/.claude/factory          → this repo (skills call ~/.claude/factory/scripts/fx.py)
#   ~/.claude/skills/factory-* → this repo's skills/*
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$HOME/.claude/skills"
ln -sfn "$here" "$HOME/.claude/factory"
for d in "$here"/skills/*/; do
  name="factory-$(basename "$d")"
  ln -sfn "${d%/}" "$HOME/.claude/skills/$name"
  echo "linked /$name"
done
chmod +x "$here/scripts/fx.py"
mkdir -p "$HOME/.local/bin"
ln -sfn "$here/scripts/fx.py" "$HOME/.local/bin/fx"
echo "linked fx → ~/.local/bin/fx"
