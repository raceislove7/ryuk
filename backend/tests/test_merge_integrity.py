"""Prevent committed conflict markers from breaking runtime, browser tests or runbooks."""

from pathlib import Path


def test_source_and_runbooks_have_no_merge_conflict_markers() -> None:
    root = Path(__file__).resolve().parents[2]
    directories = [
        "backend/app",
        "backend/tests",
        "frontend/app",
        "frontend/lib",
        "frontend/components",
        "frontend/tests",
        "docs",
    ]
    files = [
        path
        for name in directories
        for path in (root / name).rglob("*")
        if path.is_file() and path.suffix in {".py", ".ts", ".tsx", ".mjs", ".md", ".css"}
    ]
    files += list(root.glob("*.md"))
    failures = []
    for path in files:
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if line.startswith(("<<<<<<< ", ">>>>>>> ")):
                failures.append(f"{path.relative_to(root)}:{number}")
    assert not failures, "Unresolved merge markers: " + ", ".join(failures)
