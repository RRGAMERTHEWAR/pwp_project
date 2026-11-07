"""Entry point for the Customer Billing System.

HOW TO RUN:
    python main.py

FLOW:
    1. Validates Python environment and optional dependencies.
    2. Initializes SQLite database tables and default admin/cashier accounts.
    3. Launches the Login Window.
"""

from __future__ import annotations

import os
import sys


def main() -> int:
    """Validate dependencies, configure GUI theme, and launch the application."""
    # Ensure sibling packages (core, db, ui) are discoverable in Python's search path
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)

    # ---------------- Step 1: Check Built-in Tkinter ----------------
    try:
        import tkinter as _tk  # noqa: F401
        from tkinter import messagebox
    except ImportError:
        print(
            "Missing dependency: Tkinter isn't available.\n"
            "  Linux:    sudo apt install python3-tk\n"
            "  Windows/macOS: reinstall Python from python.org with the "
            "'tcl/tk and IDLE' option checked.",
            file=sys.stderr,
        )
        return 1

    # ---------------- Step 2: Check Required 3rd-Party Libraries ----------------
    try:
        import customtkinter  # noqa: F401
        import fpdf  # noqa: F401
        import matplotlib  # noqa: F401
    except ImportError as exc:
        messagebox.showerror(
            "Missing dependency",
            f"This build needs optional libraries for the modern UI, PDF "
            f"export and charts:\n{exc}\n\nInstall them with:\n"
            f"    python -m pip install -r requirements.txt",
        )
        return 1

    # ---------------- Step 3: Initialize Theme & Database ----------------
    import customtkinter as ctk
    from core.logger import logger

    from db import database
    from ui import cleanup
    from ui.login_view import LoginWindow

    # Set UI Theme ("system", "dark", or "light")
    ctk.set_appearance_mode("system")  # follows OS dark/light preference
    ctk.set_default_color_theme("blue")

    # Install safe window-closing protocols to prevent Tkinter teardown crashes
    cleanup.install()

    # Create tables and default users in billing_system.db if they don't exist yet
    database.init_db()

    # ---------------- Step 4: Show Login Window ----------------
    LoginWindow().mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())