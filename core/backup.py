"""Database Backup Utility.

Provides automated snapshot creation of the SQLite database file (`billing_system.db`).
Backups are timestamped (e.g., `backup_20261107_120000.db`) to allow safe rollbacks.
"""

import shutil
import os
from datetime import datetime
from core.logger import logger


def perform_backup(db_path: str, backup_dir: str) -> str | None:
    """Create a timestamped duplicate of the SQLite database.
    
    Args:
        db_path: Path to the active database file (e.g., 'billing_system.db').
        backup_dir: Directory where the backup copy will be stored.
        
    Returns:
        Full path to the newly created backup file, or None if failed.
    """
    if not backup_dir:
        logger.warning("Backup failed: No backup directory specified in settings.")
        return None

    try:
        # Create destination folder if it doesn't already exist
        os.makedirs(backup_dir, exist_ok=True)

        # Generate unique timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"backup_{timestamp}.db"
        dest_path = os.path.join(backup_dir, filename)

        # Copy SQLite file preserving metadata
        shutil.copy2(db_path, dest_path)
        logger.info(f"Database backup created successfully at: {dest_path}")
        return dest_path
    except Exception as e:
        logger.error(f"Database backup failed: {e}")
        return None
