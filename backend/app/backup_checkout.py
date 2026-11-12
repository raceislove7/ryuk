"""Operator-only consistent SQLite backup to a NEW private file. Never resets a ledger."""

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path


def backup_checkout(source: Path, destination: Path) -> None:
    """Read-only source; refuse overwriting any destination or following a destination symlink."""
    source = source.resolve(strict=True)
    if not source.is_file():
        raise ValueError("Source must be a ledger file")
    descriptor = os.open(destination, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    # A failed backup is retained for diagnosis, never confused with a verified success.
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(destination)) as copy:
            original.backup(copy)
            if copy.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("Backup integrity verification failed")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    backup_checkout(args.source, args.destination)
    print("Private ledger backup completed and integrity verified; source unchanged.")


if __name__ == "__main__":
    main()
