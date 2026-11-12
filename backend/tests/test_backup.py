"""Backup rehearsal uses fresh fixtures, not existing financial records."""

import sqlite3
import sys
from pathlib import Path

import pytest

from app.backup_checkout import backup_checkout


def test_backup_preserves_held_and_settled_money(tmp_path):
    source, target = tmp_path / "source.sqlite3", tmp_path / "copy.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE balances(settled,held)")
        db.execute("INSERT INTO balances VALUES(118000,139000)")
    backup_checkout(source, target)
    for path in (source, target):
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT * FROM balances").fetchone() == (118000, 139000)
    # Windows NTFS does not enforce Unix-style mode bits; skip the permission
    # assertion on Windows.  Production runs on Linux where 0o600 is enforced.
    if sys.platform != "win32":
        assert target.stat().st_mode & 0o777 == 0o600
    with pytest.raises(FileExistsError):
        backup_checkout(source, target)
    with pytest.raises(FileExistsError):
        backup_checkout(source, source)


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Symlink creation requires elevated privileges on Windows; "
    "enforced in production Linux containers.",
)
def test_backup_refuses_destination_symlink(tmp_path):
    source = tmp_path / "source.sqlite3"
    with sqlite3.connect(source) as db:
        db.execute("CREATE TABLE records(value)")
    alias: Path = tmp_path / "alias"
    alias.symlink_to(source)
    with pytest.raises(FileExistsError):
        backup_checkout(source, alias)
