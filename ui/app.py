"""Main Application Container & Sidebar Navigation.

This is the primary desktop window (`BillingApp`) hosting all sub-views.
It provides:
- Left sidebar with navigation buttons (filtered by user role: admin vs. cashier)
- Dynamic view container that swaps screens on the right
- Toast notifications and system logout functionality
"""

from __future__ import annotations

import customtkinter as ctk

from core import settings as core_settings
from ui import cleanup
from ui.analytics_view import AnalyticsView
from ui.billing_view import BillingView
from ui.history_view import HistoryView
from ui.product_view import ProductView
from ui.receipt_view import ReceiptView
from ui.settings_view import SettingsView
from ui.customer_view import CustomerView
from ui.theme import (
    apply_custom_table_styles,
    ToastNotification,
    PRIMARY,
    PRIMARY_HOVER,
    SIDEBAR_BG,
    BORDER_COLOR,
    TEXT_MAIN,
    TEXT_MUTED,
)


class BillingApp(ctk.CTk):
    """Root window with modern sidebar layout and view router.

    Navigation is gated by role: cashiers get billing, customers & history;
    admins get everything including inventory, analytics, and settings.
    """

    def __init__(self, user: dict) -> None:
        super().__init__()
        cleanup.install_close_protocol(self)
        self.user = user
        self.settings = core_settings.load()

        # ---------------- Window Sizing & Title ----------------
        self.title(f"{self.settings.store_name} — POS Billing System")
        self.geometry("1180x760")
        self.minsize(960, 640)

        # Apply cohesive ttk table styles to match CustomTkinter dark/light mode
        apply_custom_table_styles()

        self._current_view: ctk.CTkFrame | None = None
        self._current_key: str = "billing"
        self._is_fullscreen: bool = False

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # F11 fullscreen toggle & Escape to exit fullscreen
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<Escape>", lambda e: self.exit_fullscreen())

        self._build_sidebar()
        self._build_content_area()

        # Check for low stock on startup
        self._check_low_stock()

        self.show_billing()

    # -- sidebar layout -------------------------------------------------------

    def _build_sidebar(self) -> None:
        self.sidebar = ctk.CTkFrame(
            self,
            width=230,
            corner_radius=0,
            fg_color=SIDEBAR_BG,
            border_width=1,
            border_color=BORDER_COLOR,
        )
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)
        self.sidebar.grid_rowconfigure(8, weight=1)  # spacer

        # Brand header
        brand_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        brand_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(20, 16))

        ctk.CTkLabel(
            brand_frame,
            text=self.settings.store_name,
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color=TEXT_MAIN,
            anchor="w",
        ).pack(fill="x")

        role_badge = f"{self.user['role'].upper()} MODE"
        ctk.CTkLabel(
            brand_frame,
            text=f"● {role_badge}",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#10b981" if self.user["role"] == "admin" else "#3b82f6",
            anchor="w",
        ).pack(fill="x", pady=(2, 0))

        # Nav items
        self._nav_buttons: dict[str, ctk.CTkButton] = {}
        entries = [
            ("billing", "🛒  Point of Sale", lambda: self.show_billing(), False),
            ("customers", "👥  Customers", lambda: self.show_customers(), False),
            ("products", "📦  Inventory", lambda: self.show_products(), True),
            ("history", "📋  Invoices & History", lambda: self.show_history(), False),
            ("analytics", "📊  Analytics", lambda: self.show_analytics(), True),
            ("settings", "⚙️  Settings", lambda: self.show_settings(), True),
        ]

        row_idx = 1
        for key, label, command, admin_only in entries:
            if admin_only and self.user["role"] != "admin":
                continue
            btn = ctk.CTkButton(
                self.sidebar,
                text=label,
                height=42,
                corner_radius=10,
                anchor="w",
                command=command,
                fg_color="transparent",
                text_color=TEXT_MUTED,
                hover_color=("#e2e8f0", "#1e293b"),
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            btn.grid(row=row_idx, column=0, sticky="ew", padx=12, pady=3)
            self._nav_buttons[key] = btn
            row_idx += 1

        # User profile & logout box at bottom
        user_card = ctk.CTkFrame(
            self.sidebar,
            corner_radius=12,
            fg_color=("#f1f5f9", "#1e293b"),
            border_width=1,
            border_color=BORDER_COLOR,
        )
        user_card.grid(row=9, column=0, sticky="ew", padx=12, pady=(0, 16))

        username_display = self.user.get("full_name") or self.user.get("username")
        ctk.CTkLabel(
            user_card,
            text=f"👤 {username_display}",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MAIN,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 2))

        # Appearance mode switcher & Logout
        footer_actions = ctk.CTkFrame(user_card, fg_color="transparent")
        footer_actions.pack(fill="x", padx=12, pady=(4, 10))

        theme_btn = ctk.CTkButton(
            footer_actions,
            text="🌓",
            width=32,
            height=30,
            corner_radius=8,
            fg_color="transparent",
            hover_color=("#e2e8f0", "#334155"),
            text_color=TEXT_MAIN,
            command=self._toggle_theme,
        )
        theme_btn.pack(side="left")

        logout_btn = ctk.CTkButton(
            footer_actions,
            text="Sign out",
            height=30,
            corner_radius=8,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._logout,
        )
        logout_btn.pack(side="right", fill="x", expand=True, padx=(8, 0))

    def _build_content_area(self) -> None:
        self.content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew")
        self.content_frame.grid_columnconfigure(0, weight=1)
        self.content_frame.grid_rowconfigure(0, weight=1)

    def _toggle_theme(self) -> None:
        mode = "Light" if ctk.get_appearance_mode().lower() == "dark" else "Dark"
        ctk.set_appearance_mode(mode)
        apply_custom_table_styles()
        ToastNotification.show(self, f"Theme switched to {mode} mode", kind="info", duration_ms=1800)

    def notify(self, message: str, kind: str = "success") -> None:
        """Display a modern toast alert."""
        ToastNotification.show(self, message, kind=kind)

    def _highlight(self, key: str) -> None:
        self._current_key = key
        for k, btn in self._nav_buttons.items():
            if k == key:
                btn.configure(
                    fg_color=PRIMARY,
                    text_color="#ffffff",
                    hover_color=PRIMARY_HOVER,
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=TEXT_MUTED,
                    hover_color=("#e2e8f0", "#1e293b"),
                )

    # -- view swapping --------------------------------------------------------

    def _swap(self, new_view: ctk.CTkFrame) -> None:
        if self._current_view is not None:
            self._current_view.destroy()
        self._current_view = new_view
        new_view.grid(row=0, column=0, sticky="nsew")

    def show_billing(self) -> None:
        self._highlight("billing")
        self._swap(BillingView(self.content_frame, self))

    def show_receipt(self, bill) -> None:
        self._swap(ReceiptView(self.content_frame, self, bill))

    def show_customers(self) -> None:
        self._highlight("customers")
        self._swap(CustomerView(self.content_frame, self))

    def show_products(self) -> None:
        if self.user["role"] != "admin":
            return
        self._highlight("products")
        self._swap(ProductView(self.content_frame, self))

    def show_history(self) -> None:
        self._highlight("history")
        self._swap(HistoryView(self.content_frame, self))

    def show_analytics(self) -> None:
        if self.user["role"] != "admin":
            return
        self._highlight("analytics")
        self._swap(AnalyticsView(self.content_frame, self))

    def show_settings(self) -> None:
        if self.user["role"] != "admin":
            return
        self._highlight("settings")
        self._swap(SettingsView(self.content_frame, self))

    def toggle_fullscreen(self) -> None:
        """Toggle window between fullscreen and standard windowed mode."""
        self._is_fullscreen = not self._is_fullscreen
        self.attributes("-fullscreen", self._is_fullscreen)
        mode_text = "Fullscreen mode enabled (Press F11 or Esc to exit)" if self._is_fullscreen else "Windowed mode restored"
        self.notify(mode_text, kind="info")

    def exit_fullscreen(self) -> None:
        """Exit fullscreen mode if currently in fullscreen."""
        if self._is_fullscreen:
            self._is_fullscreen = False
            self.attributes("-fullscreen", False)
            self.notify("Windowed mode restored", kind="info")

    # -- misc -----------------------------------------------------------------

    def destroy(self) -> None:
        """Cancel pending after() timers before tearing the window down."""
        cleanup.cancel_all()
        super().destroy()

    def _logout(self) -> None:
        """Prompt shift summary on logout for cashier reconciliation."""
        from datetime import datetime
        from db import database
        from tkinter import messagebox

        today = datetime.now().strftime("%Y-%m-%d")
        revenue, count, sold = database.revenue_for_period_custom(today, today)
        currency = self.settings.currency

        # Open Shift Handover modal
        win = ctk.CTkToplevel(self)
        win.title("Shift Handover & Drawer Audit")
        win.geometry("380x360")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(win, text="💼 Cashier Shift Handover", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(18, 4))
        ctk.CTkLabel(win, text=f"Cashier: {self.user.get('full_name') or self.user.get('username')}", font=ctk.CTkFont(size=12), text_color="gray").pack(pady=(0, 12))

        card = ctk.CTkFrame(win, corner_radius=10)
        card.pack(fill="x", padx=24, pady=8)
        card.grid_columnconfigure(0, weight=1)

        stats = [
            ("Transactions Processed:", str(count)),
            ("Items Handled:", str(sold)),
            ("Total Sales Collected:", f"{currency}{revenue:,.2f}"),
        ]
        for row_i, (lbl, val) in enumerate(stats):
            ctk.CTkLabel(card, text=lbl, font=ctk.CTkFont(size=12)).grid(row=row_i, column=0, sticky="w", padx=12, pady=6)
            ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=12, weight="bold")).grid(row=row_i, column=1, sticky="e", padx=12, pady=6)

        def proceed_logout():
            win.destroy()
            self.destroy()
            from ui.login_view import LoginWindow
            LoginWindow().mainloop()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=(20, 10))

        ctk.CTkButton(btn_row, text="Confirm & Sign Out", width=140, height=34, corner_radius=8, fg_color=("#ef4444", "#dc2626"), hover_color="#dc2626", command=proceed_logout).pack(side="left", padx=4)
        ctk.CTkButton(btn_row, text="Cancel", width=90, height=34, corner_radius=8, fg_color="#64748b", hover_color="#475569", command=win.destroy).pack(side="left", padx=4)

    def refresh_low_stock_badge(self) -> None:
        """Update the low stock counter on the inventory button."""
        if "products" not in self._nav_buttons:
            return
        from db import database
        low_stock_items = database.get_low_stock_products()
        count = len(low_stock_items)
        if count > 0:
            self._nav_buttons["products"].configure(text=f"📦  Inventory  ({count} low)")
        else:
            self._nav_buttons["products"].configure(text="📦  Inventory")

    def _check_low_stock(self) -> None:
        """Notify user if any products are below low stock threshold and update badge."""
        if self.user["role"] != "admin":
            return
        from db import database
        self.refresh_low_stock_badge()
        low_stock_items = database.get_low_stock_products()
        if low_stock_items:
            names = ", ".join([i["name"] for i in low_stock_items[:3]])
            count = len(low_stock_items)
            self.after(
                600,
                lambda: self.notify(
                    f"⚠️ Low Stock Alert: {count} item(s) need restock ({names}...)",
                    kind="warning",
                ),
            )