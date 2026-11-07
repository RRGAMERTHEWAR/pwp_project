"""Login screen with role-based authentication.

This module provides the LoginWindow, which is the first screen the user sees.
It handles credential verification against the SQLite database and routes the
user into the main application (`ui.app.BillingApp`).
"""

from __future__ import annotations

import customtkinter as ctk

from db import database
from ui import cleanup

# Explanations of what permissions each role has in the application
_ROLE_DESCRIPTION = {
    "admin": "Administrator — full access (billing, inventory, settings, analytics)",
    "cashier": "Cashier — create bills and search bill history",
}


class LoginWindow(ctk.CTk):
    """Root window shown first; launches :class:`ui.app.BillingApp` on success."""

    def __init__(self) -> None:
        super().__init__()
        # Ensure timers and background cleanup tasks terminate gracefully on window close
        cleanup.install_close_protocol(self)

        # ---------------- Window Setup ----------------
        self.title("Login — Customer Billing System")
        self.geometry("440x520")
        self.resizable(False, False)
        self.grid_columnconfigure(0, weight=1)

        # ---------------- Header Titles ----------------
        ctk.CTkLabel(
            self, text="⚡ POS Retail Suite", font=ctk.CTkFont(size=26, weight="bold")
        ).grid(row=0, column=0, pady=(36, 4))
        ctk.CTkLabel(
            self, text="Sign in to your point-of-sale terminal", font=ctk.CTkFont(size=12), text_color="gray"
        ).grid(row=1, column=0, pady=(0, 20))

        # ---------------- Main Form Box ----------------
        form = ctk.CTkFrame(self, corner_radius=14)
        form.grid(row=2, column=0, padx=36, sticky="ew")
        form.grid_columnconfigure(0, weight=1)

        # Username Input
        ctk.CTkLabel(form, text="Username", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=0, column=0, sticky="ew", padx=22, pady=(20, 4)
        )
        self.username_var = ctk.StringVar()
        username_entry = ctk.CTkEntry(
            form, textvariable=self.username_var, height=36, corner_radius=8, placeholder_text="Enter username"
        )
        username_entry.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 12))
        username_entry.focus_set()

        # Password Input
        ctk.CTkLabel(form, text="Password", anchor="w", font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, sticky="ew", padx=22, pady=(0, 4)
        )
        self.password_var = ctk.StringVar()
        self.password_entry = ctk.CTkEntry(
            form, textvariable=self.password_var, show="*", height=36, corner_radius=8, placeholder_text="Enter password"
        )
        self.password_entry.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 16))
        # Allow pressing Enter key in the password field to submit
        self.password_entry.bind("<Return>", lambda _e: self._do_login())

        # Submit Button
        ctk.CTkButton(
            form,
            text="Sign in to Terminal",
            command=self._do_login,
            height=40,
            corner_radius=8,
            fg_color=("#3b82f6", "#2563eb"),
            hover_color=("#2563eb", "#1d4ed8"),
            font=ctk.CTkFont(size=13, weight="bold"),
        ).grid(row=4, column=0, sticky="ew", padx=22, pady=(4, 12))

        # Error Message Label (shows 'Invalid username or password' if failed)
        self.error_var = ctk.StringVar()
        ctk.CTkLabel(
            form, textvariable=self.error_var, text_color="#ef4444",
            font=ctk.CTkFont(size=12),
        ).grid(row=5, column=0, sticky="ew", padx=22, pady=(0, 8))

        # ---------------- Quick Demo Fast-Fill Buttons ----------------
        # Handy buttons for testing without typing credentials manually
        demo_frame = ctk.CTkFrame(self, fg_color="transparent")
        demo_frame.grid(row=3, column=0, pady=(20, 0))

        ctk.CTkLabel(
            demo_frame, text="Quick login for testing:", font=ctk.CTkFont(size=11), text_color="gray"
        ).pack()

        btn_row = ctk.CTkFrame(demo_frame, fg_color="transparent")
        btn_row.pack(pady=4)

        ctk.CTkButton(
            btn_row,
            text="Admin demo",
            width=100,
            height=26,
            corner_radius=6,
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            hover_color=("#cbd5e1", "#475569"),
            font=ctk.CTkFont(size=11),
            command=lambda: self._set_creds("admin", "admin123"),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            btn_row,
            text="Cashier demo",
            width=100,
            height=26,
            corner_radius=6,
            fg_color=("#e2e8f0", "#334155"),
            text_color=("#1e293b", "#f8fafc"),
            hover_color=("#cbd5e1", "#475569"),
            font=ctk.CTkFont(size=11),
            command=lambda: self._set_creds("cashier", "cash123"),
        ).pack(side="left", padx=4)

    def _set_creds(self, u: str, p: str) -> None:
        """Helper to fill in username and password fields quickly."""
        self.username_var.set(u)
        self.password_var.set(p)

    def _do_login(self) -> None:
        """Validate credentials against the database and transition to the app."""
        username = self.username_var.get().strip()
        password = self.password_var.get()
        user = database.verify_login(username, password)
        if user is None:
            self.error_var.set("Invalid username or password")
            self.password_var.set("")
            self.password_entry.focus_set()
            return
        self.error_var.set("")
        self._launch_app(user)

    def _launch_app(self, user: dict) -> None:
        """Close the login window and launch the main BillingApp window."""
        from ui.app import BillingApp

        self.destroy()
        app = BillingApp(user)
        app.mainloop()

    def destroy(self) -> None:
        """Cancel pending after() timers before tearing the login window down."""
        cleanup.cancel_all()
        super().destroy()
