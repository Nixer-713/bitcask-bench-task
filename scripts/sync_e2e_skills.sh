#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
codex_home="${CODEX_HOME:-$HOME/.codex}"
dest_root="$codex_home/skills"

mkdir -p "$dest_root"

for skill_dir in "$repo_root"/skills/e2e-*; do
  [ -d "$skill_dir" ] || continue
  name="$(basename "$skill_dir")"
  rm -rf "$dest_root/$name"
  cp -R "$skill_dir" "$dest_root/$name"
done

python3 - <<'PY'
from pathlib import Path
import os
import re
import sys

root = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills"
for path in sorted(root.glob("e2e-*/SKILL.md")):
    text = path.read_text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not match:
        print(f"invalid frontmatter: {path}", file=sys.stderr)
        sys.exit(1)
    frontmatter = match.group(1)
    name_match = re.search(r"^name:\s*(.+)$", frontmatter, re.M)
    desc_match = re.search(r"^description:\s*(.+)$", frontmatter, re.M)
    if not name_match or not desc_match:
        print(f"missing name/description: {path}", file=sys.stderr)
        sys.exit(1)
    name = name_match.group(1).strip().strip('"')
    desc = desc_match.group(1).strip().strip('"')
    if not re.fullmatch(r"[a-z0-9-]+", name):
        print(f"invalid skill name {name!r}: {path}", file=sys.stderr)
        sys.exit(1)
    if not desc.startswith("Use when"):
        print(f"description must start with 'Use when': {path}", file=sys.stderr)
        sys.exit(1)
    print(f"installed {name}")
PY

echo "Restart Codex to refresh the skill list."
