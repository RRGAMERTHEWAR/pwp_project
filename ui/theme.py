"""Theme and styling helper for the Billing System.

Provides modern dark/light palettes, font standards, and ttk Treeview styling
so tables match CustomTkinter's sleek aesthetic.

HOW TO EDIT COLORS:
- Each color tuple is defined as `(LIGHT_MODE_COLOR, DARK_MODE_COLOR)`.
- Simply replace the hex strings below to change the app's look and feel!
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

# ==========================================
# Accent & Brand Colors (Buttons, Highlights)
# Format: ("LIGHT_MODE_HEX", "DARK_MODE_HEX")
# ==========================================
PRIMARY = ("#3b82f6", "#2563eb")       # Modern Royal Blue (Main action buttons)
PRIMARY_HOVER = ("#2563eb", "#1d4ed8") # Button hover state
SUCCESS = ("#10b981", "#059669")       # Emerald / Green (Generate Bill, Save)
SUCCESS_HOVER = ("#059669", "#047857")
DANGER = ("#ef4444", "#dc2626")        # Rose / Coral (Delete, Clear, Reset)
DANGER_HOVER = ("#dc2626", "#b91c1c")
WARNING = ("#f59e0b", "#d97706")       # Amber (Alerts, low stock notices)

# ==========================================
# Neutral Backgrounds & Card Panels
# ==========================================
SIDEBAR_BG = ("#f8fafc", "#0f172a")    # Left sidebar background (Slate 50 / Slate 900)
SURFACE_BG = ("#ffffff", "#1e293b")    # Card / panel background (White / Slate 800)
BORDER_COLOR = ("#e2e8f0", "#334155")  # Card outlines & separators
TEXT_MUTED = ("#64748b", "#94a3b8")    # Subtitles and placeholder text
TEXT_MAIN = ("#0f172a", "#f8fafc")     # Primary readable text (Dark slate / Clean white)


def apply_custom_table_styles() -> None:
    """Configures the ttk.Treeview widget to blend seamlessly with CustomTkinter."""
    style = ttk.Style()
    current_mode = ctk.get_appearance_mode()
    is_dark = current_mode.lower() == "dark"

    bg_color = "#1e293b" if is_dark else "#ffffff"
    fg_color = "#f8fafc" if is_dark else "#0f172a"
    header_bg = "#0f172a" if is_dark else "#f1f5f9"
    header_fg = "#94a3b8" if is_dark else "#475569"
    selected_bg = "#2563eb" if is_dark else "#3b82f6"
    selected_fg = "#ffffff"

    style.theme_use("clam")

    # Configure Treeview table
    style.configure(
        "Treeview",
        background=bg_color,
        foreground=fg_color,
        fieldbackground=bg_color,
        rowheight=32,
        font=("Segoe UI", 10),
        borderwidth=0,
    )
    style.map(
        "Treeview",
        background=[("selected", selected_bg)],
        foreground=[("selected", selected_fg)],
    )

    # Configure Treeview Header
    style.configure(
        "Treeview.Heading",
        background=header_bg,
        foreground=header_fg,
        relief="flat",
        font=("Segoe UI", 10, "bold"),
        padding=(8, 6),
    )
    style.map(
        "Treeview.Heading",
        background=[("active", selected_bg if is_dark else "#e2e8f0")],
        foreground=[("active", "#ffffff" if is_dark else "#0f172a")],
    )


class ToastNotification:
    """Smooth non-blocking toast notification that slides in and auto-dismisses."""

    @classmethod
    def show(
        cls,
        parent: tk.Tk | ctk.CTk | ctk.CTkFrame,
        message: str,
        kind: str = "success",
        duration_ms: int = 2500,
    ) -> None:
        colors = {
            "success": ("#10b981", "#ffffff"),
            "error": ("#ef4444", "#ffffff"),
            "info": ("#3b82f6", "#ffffff"),
            "warning": ("#f59e0b", "#ffffff"),
        }
        bg, fg = colors.get(kind, colors["info"])

        # Create overlay toast frame on top of window
        toast = ctk.CTkFrame(
            parent,
            fg_color=bg,
            corner_radius=10,
            border_width=0,
        )
        label = ctk.CTkLabel(
            toast,
            text=message,
            text_color=fg,
            font=ctk.CTkFont(size=12, weight="bold"),
            padx=16,
            pady=10,
        )
        label.pack()

        # Place toast near the top right of the parent
        toast.place(relx=0.98, rely=0.03, anchor="ne")

        def dismiss():
            try:
                toast.destroy()
            except Exception:
                pass

        parent.after(duration_ms, dismiss)
