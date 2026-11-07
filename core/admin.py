"""Administration & Security Audit Utilities.

Provides functions for database backup and tracking critical administrative operations
(such as deleting products, altering users, or editing store settings).
"""

from __future__ import annotations

import datetime
import os
import shutil

from db.database import DB_PATH, connect


def backup_database(backup_dir: str) -> str:
    """Copy the active SQLite database to a backup directory with a timestamp.
    
    Args:
        backup_dir: The directory where the backup file should be saved.

    Returns:
        The absolute path to the generated backup database.
    """
    if not backup_dir or not os.path.isdir(backup_dir):
        raise OSError("Invalid or missing backup directory.")
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"billing_system_backup_{timestamp}.db"
    dest_path = os.path.join(backup_dir, filename)
    
    shutil.copy2(DB_PATH, dest_path)
    return dest_path


def log_audit_action(user_id: int | None, action: str) -> None:
    """Insert an entry into the audit_logs table for administrative compliance.
    
    Args:
        user_id: The ID of the logged-in administrator performing the action.
        action: Human-readable description of what was changed or performed.
    """
    timestamp = datetime.datetime.now().isoformat(timespec="seconds")
    with connect() as conn:
        conn.execute(
            "INSERT INTO audit_logs (user_id, action, timestamp) VALUES (?, ?, ?)",
            (user_id, action, timestamp)
        )
