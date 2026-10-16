#!/usr/bin/env python3
"""Fail when production sources contain forbidden Unicode dash punctuation.

Rendered Playwright checks complement this static check by inspecting text,
accessible attributes, dynamic states and CSS generated content.
"""

from pathlib import Path
import sys


REPOSITORY = Path(__file__).resolve().parents[1]
ROOTS = (
    REPOSITORY / "web" / "src",
    REPOSITORY / "backend" / "app",
    REPOSITORY / "extension",
)
EXTENSIONS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".mjs",
    ".cjs",
    ".html",
    ".htm",
    ".css",
    ".scss",
    ".json",
    ".py",
    ".svg",
}
SKIP = {"node_modules", ".next", "dist", "build", "coverage", "__pycache__", ".venv", "vendor"}
FORBIDDEN = {chr(0x2014): "em dash U+2014", chr(0x2013): "en dash U+2013"}


def main() -> int:
    hits: list[tuple[Path, int, str, str]] = []
    for root in ROOTS:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in EXTENSIONS or SKIP.intersection(path.parts):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            for line_number, line in enumerate(lines, start=1):
                for character, description in FORBIDDEN.items():
                    if character in line:
                        hits.append((path.relative_to(REPOSITORY), line_number, description, line.strip()[:160]))

    for path, line_number, description, value in hits:
        print(f"{path}:{line_number}: {description}: {value}")
    print(f"Static forbidden-dash hits: {len(hits)}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
