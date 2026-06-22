"""Validate all SKILL.md files in the skills/ directory."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parent.parent / "skills"
errors: list[tuple[Path, str]] = []

for skill_file in sorted(root.rglob("SKILL.md")):
    text = skill_file.read_text(encoding="utf-8")

    if not text.startswith("---"):
        errors.append((skill_file, "missing frontmatter"))
        continue

    parts = text.split("---", 2)
    if len(parts) < 3:
        errors.append((skill_file, "invalid frontmatter block"))
        continue

    frontmatter = parts[1]
    body = parts[2]

    if not re.search(r"^name:\s*[\w-]+", frontmatter, re.MULTILINE):
        errors.append((skill_file, "missing or invalid name"))

    if not re.search(r"^description:\s*.+", frontmatter, re.MULTILINE):
        errors.append((skill_file, "missing description"))

    if not re.search(r"^keywords:\s*\[.*\]", frontmatter, re.MULTILINE):
        errors.append((skill_file, "missing or invalid keywords"))

    if not re.search(r"^version:\s*[\d.]+", frontmatter, re.MULTILINE):
        errors.append((skill_file, "missing version"))

    for section in ["## Trigger", "## Workflow", "## Output"]:
        if section not in body:
            errors.append((skill_file, f"missing {section}"))

if errors:
    for path, error in errors:
        print(f"FAIL: {path.relative_to(root.parent)} — {error}")
    print(f"\n{len(errors)} error(s) found.")
    sys.exit(1)

print(f"OK: {sum(1 for _ in root.rglob('SKILL.md'))} skills valid.")
