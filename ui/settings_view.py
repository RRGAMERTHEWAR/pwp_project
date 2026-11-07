"""Store Settings & User Management View (Admin Only).

Organized into 3 main tabs:
1. 'Store & Billing': Edit Store Name, Currency Symbol, Tax Rate (%), and Discount Tiers.
2. 'System & Security': Configure Database backup directories and view audit logs.
3. 'Users': Add new cashier/admin accounts, reset passwords, or remove user profiles.
"""

from __future__ import annotations

from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core import settings as core_settings
from core.settings import Settings
from db import database

if TYPE_CHECKING:  # pragma: no cover
    from ui.app import BillingApp


class SettingsView(ctk.CTkFrame):
    """Admin screen for business rules and user accounts."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp") -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            self, text="Settings", font=ctk.CTkFont(size=18, weight="bold")
        ).grid(row=0, column=0, sticky="w", padx=14, pady=(14, 6))

        tabs = ctk.CTkTabview(self)
        tabs.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 14))
        tabs.grid_columnconfigure(0, weight=1)
        tabs.grid_rowconfigure(0, weight=1)

        self._build_business_tab(tabs.add("Store & Billing"))
        self._build_security_tab(tabs.add("System & Security"))
        self._build_users_tab(tabs.add("Users"))

    # -- business rules tab ---------------------------------------------------

    def _build_business_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(1, weight=1)
        parent.grid_rowconfigure(3, weight=1)
        settings = self.app.settings

        ctk.CTkLabel(parent, text="Store name:").grid(row=0, column=0, sticky="w", padx=12, pady=6)
        self.store_var = ctk.StringVar(value=settings.store_name)
        ctk.CTkEntry(parent, textvariable=self.store_var, width=220).grid(
            row=0, column=1, sticky="w", padx=12, pady=6
        )

        ctk.CTkLabel(parent, text="Currency symbol:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.currency_var = ctk.StringVar(value=settings.currency)
        ctk.CTkEntry(parent, textvariable=self.currency_var, width=80).grid(
            row=1, column=1, sticky="w", padx=12, pady=6
        )

        rates = ctk.CTkFrame(parent, fg_color="transparent")
        rates.grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(rates, text="Tax rate (%):").pack(side="left")
        self.tax_var = ctk.StringVar(value=f"{settings.tax_rate}")
        ctk.CTkEntry(rates, textvariable=self.tax_var, width=70).pack(side="left", padx=6)
        ctk.CTkLabel(rates, text="Points per ₹100:").pack(side="left", padx=(16, 0))
        self.per100_var = ctk.StringVar(value=f"{settings.loyalty_points_per_100}")
        ctk.CTkEntry(rates, textvariable=self.per100_var, width=70).pack(side="left", padx=6)
        ctk.CTkLabel(rates, text="Point value:").pack(side="left", padx=(16, 0))
        self.rate_var = ctk.StringVar(value=f"{settings.loyalty_redemption_rate}")
        ctk.CTkEntry(rates, textvariable=self.rate_var, width=70).pack(side="left", padx=6)
        
        pay_methods_frame = ctk.CTkFrame(parent, fg_color="transparent")
        pay_methods_frame.grid(row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(pay_methods_frame, text="Payment Methods (comma-separated):").pack(side="left")
        self.payment_methods_var = ctk.StringVar(value=", ".join(settings.payment_methods))
        ctk.CTkEntry(pay_methods_frame, textvariable=self.payment_methods_var, width=400).pack(side="left", padx=6)

        pay_details_frame = ctk.CTkFrame(parent, fg_color="transparent")
        pay_details_frame.grid(row=4, column=0, columnspan=2, sticky="ew", padx=12, pady=6)
        ctk.CTkLabel(pay_details_frame, text="Store UPI ID:").pack(side="left")
        self.upi_id_var = ctk.StringVar(value=getattr(settings, "upi_id", "store@upi"))
        ctk.CTkEntry(pay_details_frame, textvariable=self.upi_id_var, width=160).pack(side="left", padx=6)

        ctk.CTkLabel(pay_details_frame, text="Bank Details:").pack(side="left", padx=(12, 0))
        self.bank_details_var = ctk.StringVar(value=settings.bank_details)
        ctk.CTkEntry(pay_details_frame, textvariable=self.bank_details_var, width=160).pack(side="left", padx=6)

        ctk.CTkLabel(pay_details_frame, text="Crypto:").pack(side="left", padx=(12, 0))
        self.crypto_wallet_var = ctk.StringVar(value=settings.crypto_wallet)
        ctk.CTkEntry(pay_details_frame, textvariable=self.crypto_wallet_var, width=160).pack(side="left", padx=6)

        tiers_box = ctk.CTkFrame(parent, corner_radius=10)
        tiers_box.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=12, pady=(12, 6))
        tiers_box.grid_columnconfigure(0, weight=1)
        tiers_box.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(tiers_box, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 2))
        ctk.CTkLabel(
            header, text="Discount tiers (minimum subtotal → percent off)",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).pack(side="left")
        ctk.CTkButton(
            header, text="+ Add tier", width=90, command=self._add_tier
        ).pack(side="right")

        self.tiers_frame = ctk.CTkScrollableFrame(tiers_box, fg_color="transparent")
        self.tiers_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.tiers_frame.grid_columnconfigure(1, weight=1)

        self._tier_rows: list[tuple[ctk.CTkFrame, ctk.StringVar, ctk.StringVar]] = []
        for min_amount, pct in settings.discount_tiers:
            self._add_tier(str(min_amount), str(pct))

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))
        ctk.CTkButton(footer, text="Save settings", width=140, command=self._save_settings).pack(side="right")

    def _add_tier(self, min_amount: str = "", pct: str = "") -> None:
        row = len(self._tier_rows)
        frame = ctk.CTkFrame(self.tiers_frame, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=2)
        frame.grid_columnconfigure(1, weight=1)

        min_var = ctk.StringVar(value=min_amount)
        pct_var = ctk.StringVar(value=pct)
        ctk.CTkLabel(frame, text="Minimum subtotal:").grid(row=0, column=0, padx=(4, 4))
        ctk.CTkEntry(frame, textvariable=min_var, width=90).grid(row=0, column=1, sticky="w", padx=4)
        ctk.CTkLabel(frame, text="Percent:").grid(row=0, column=2, padx=(12, 4))
        ctk.CTkEntry(frame, textvariable=pct_var, width=70).grid(row=0, column=3, padx=4)
        ctk.CTkButton(
            frame, text="✕", width=26, fg_color="transparent", hover_color="#e74c3c",
            command=lambda r=row: self._remove_tier(r),
        ).grid(row=0, column=4, padx=(8, 2))
        self._tier_rows.append((frame, min_var, pct_var))

    def _remove_tier(self, row_idx: int) -> None:
        frame, _, _ = self._tier_rows.pop(row_idx)
        frame.destroy()
        for i, (fr, _mv, _pv) in enumerate(self._tier_rows):
            fr.grid(row=i, column=0, sticky="ew", pady=2)

    def _collect_settings(self) -> Settings:
        settings = Settings(
            store_name=self.store_var.get(),
            currency=self.currency_var.get(),
            tax_rate=float(self.tax_var.get()),
            loyalty_points_per_100=int(self.per100_var.get()),
            loyalty_redemption_rate=float(self.rate_var.get()),
            payment_methods=[p.strip() for p in self.payment_methods_var.get().split(",") if p.strip()],
            upi_id=self.upi_id_var.get().strip(),
            bank_details=self.bank_details_var.get(),
            crypto_wallet=self.crypto_wallet_var.get(),
            discount_tiers=[
                [float(mv.get()), float(pv.get())] for _fr, mv, pv in self._tier_rows
            ],
        )
        return settings

    def _save_settings(self) -> None:
        try:
            settings = self._collect_settings()
            settings.validate()
        except (ValueError, TypeError) as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        try:
            core_settings.save(settings)
        except OSError as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.app.settings = settings
        messagebox.showinfo("Saved", "Settings saved to config.json and applied.")

    # -- security tab ---------------------------------------------------------

    def _build_security_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(1, weight=1)
        settings = self.app.settings

        # Backup section
        ctk.CTkLabel(parent, text="Database Backup", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))
        
        ctk.CTkLabel(parent, text="Backup directory:").grid(row=1, column=0, sticky="w", padx=12, pady=6)
        self.backup_var = ctk.StringVar(value=settings.backup_dir)
        backup_frame = ctk.CTkFrame(parent, fg_color="transparent")
        backup_frame.grid(row=1, column=1, sticky="ew", padx=12, pady=6)
        backup_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkEntry(backup_frame, textvariable=self.backup_var).grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkButton(backup_frame, text="Browse", width=70, command=self._browse_backup).grid(row=0, column=1)
        
        btn_backup_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_backup_row.grid(row=2, column=1, sticky="w", padx=12, pady=6)
        ctk.CTkButton(btn_backup_row, text="💾 Backup Now", width=130, command=self._run_backup).pack(side="left")
        ctk.CTkButton(btn_backup_row, text="📥 Restore Database", width=140, fg_color="#ef4444", hover_color="#dc2626", command=self._run_restore).pack(side="left", padx=8)

        # SMTP section
        ctk.CTkLabel(parent, text="Email / SMTP Configuration", font=ctk.CTkFont(weight="bold")).grid(row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(24, 6))
        
        ctk.CTkLabel(parent, text="SMTP Server:").grid(row=4, column=0, sticky="w", padx=12, pady=6)
        self.smtp_server_var = ctk.StringVar(value=settings.smtp_server)
        ctk.CTkEntry(parent, textvariable=self.smtp_server_var, width=220).grid(row=4, column=1, sticky="w", padx=12, pady=6)

        ctk.CTkLabel(parent, text="SMTP Port:").grid(row=5, column=0, sticky="w", padx=12, pady=6)
        self.smtp_port_var = ctk.StringVar(value=str(settings.smtp_port))
        ctk.CTkEntry(parent, textvariable=self.smtp_port_var, width=80).grid(row=5, column=1, sticky="w", padx=12, pady=6)

        ctk.CTkLabel(parent, text="SMTP Username:").grid(row=6, column=0, sticky="w", padx=12, pady=6)
        self.smtp_user_var = ctk.StringVar(value=settings.smtp_user)
        ctk.CTkEntry(parent, textvariable=self.smtp_user_var, width=220).grid(row=6, column=1, sticky="w", padx=12, pady=6)

        ctk.CTkLabel(parent, text="SMTP Password:").grid(row=7, column=0, sticky="w", padx=12, pady=6)
        self.smtp_pass_var = ctk.StringVar(value=settings.smtp_pass)
        ctk.CTkEntry(parent, textvariable=self.smtp_pass_var, show="*", width=220).grid(row=7, column=1, sticky="w", padx=12, pady=6)

        ctk.CTkButton(parent, text="Save Security Settings", width=160, command=self._save_security_settings).grid(row=8, column=1, sticky="w", padx=12, pady=(24, 12))

    def _browse_backup(self) -> None:
        import tkinter.filedialog
        d = tkinter.filedialog.askdirectory()
        if d:
            self.backup_var.set(d)

    def _run_backup(self) -> None:
        b_dir = self.backup_var.get()
        if not b_dir:
            messagebox.showerror("Backup", "Please select a backup directory first.")
            return
        try:
            from core import backup
            from db import database
            path = backup.perform_backup(database.DB_PATH, b_dir)
            if path:
                messagebox.showinfo("Backup Success", f"Database backed up to:\n{path}")
            else:
                messagebox.showerror("Backup Error", "Backup failed. Check app.log for details.")
        except Exception as e:
            messagebox.showerror("Backup Error", str(e))

    def _run_restore(self) -> None:
        """Restore database from a previously saved .db or .zip backup."""
        import tkinter.filedialog
        import shutil
        from db import database

        path = tkinter.filedialog.askopenfilename(
            parent=self,
            title="Select Backup Database File to Restore",
            filetypes=[("Database & Backup files", "*.db;*.sqlite;*.zip"), ("All files", "*.*")],
        )
        if not path:
            return

        if not messagebox.askyesno(
            "Confirm Database Restore",
            "WARNING: Restoring will overwrite the current active database with the selected backup.\n\n"
            "Are you sure you want to proceed?",
        ):
            return

        try:
            shutil.copy2(path, database.DB_PATH)
            messagebox.showinfo(
                "Restore Successful",
                "Database restored successfully!\nPlease restart the application to reload all restored records.",
            )
            self.app.notify("Database restored successfully!", kind="success")
        except Exception as exc:
            messagebox.showerror("Restore Failed", f"Could not restore database:\n{exc}")

    def _save_security_settings(self) -> None:
        settings = self.app.settings
        settings.backup_dir = self.backup_var.get()
        settings.smtp_server = self.smtp_server_var.get()
        try:
            settings.smtp_port = int(self.smtp_port_var.get() or 587)
        except ValueError:
            messagebox.showerror("Invalid Input", "SMTP Port must be a number.")
            return
        settings.smtp_user = self.smtp_user_var.get()
        settings.smtp_pass = self.smtp_pass_var.get()
        try:
            settings.validate()
            core_settings.save(settings)
            messagebox.showinfo("Saved", "System & Security settings saved.")
            from core import admin
            admin.log_audit_action(self.app.user.get("id"), "Updated Security Settings")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # -- users tab ------------------------------------------------------------

    def _build_users_tab(self, parent: ctk.CTkFrame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        parent.grid_rowconfigure(2, weight=1)

        form = ctk.CTkFrame(parent, corner_radius=10)
        form.grid(row=0, column=0, sticky="ew", padx=10, pady=8)
        self.u_username = ctk.StringVar()
        self.u_password = ctk.StringVar()
        self.u_fullname = ctk.StringVar()
        self.u_role = ctk.StringVar(value="cashier")

        ctk.CTkLabel(form, text="Username:").grid(row=0, column=0, padx=(10, 2), pady=8)
        ctk.CTkEntry(form, textvariable=self.u_username, width=120).grid(row=0, column=1, padx=4, pady=8)
        ctk.CTkLabel(form, text="Password:").grid(row=0, column=2, padx=(10, 2), pady=8)
        ctk.CTkEntry(form, textvariable=self.u_password, show="*", width=120).grid(row=0, column=3, padx=4, pady=8)
        ctk.CTkLabel(form, text="Full name:").grid(row=0, column=4, padx=(10, 2), pady=8)
        ctk.CTkEntry(form, textvariable=self.u_fullname, width=130).grid(row=0, column=5, padx=4, pady=8)
        ctk.CTkOptionMenu(form, values=["cashier", "admin"], variable=self.u_role, width=110).grid(
            row=0, column=6, padx=4, pady=8
        )
        ctk.CTkButton(form, text="Add user", width=90, command=self._add_user).grid(
            row=0, column=7, padx=(8, 10), pady=8
        )

        table_frame = ctk.CTkFrame(parent, corner_radius=10)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.user_tree = ttk.Treeview(
            table_frame, columns=("id", "username", "full_name", "role"),
            show="headings", selectmode="browse",
        )
        for col, text in [("id", "ID"), ("username", "Username"), ("full_name", "Full name"), ("role", "Role")]:
            self.user_tree.heading(col, text=text)
        self.user_tree.column("id", width=50, stretch=False)
        self.user_tree.column("username", width=140)
        self.user_tree.column("full_name", width=180)
        self.user_tree.column("role", width=100)
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.user_tree.yview)
        self.user_tree.configure(yscrollcommand=yscroll.set)
        self.user_tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        yscroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

        actions = ctk.CTkFrame(parent, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        ctk.CTkButton(actions, text="Delete", fg_color="#c0392b", width=90, command=self._delete_user).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Change role", width=110, command=self._change_role).pack(side="left", padx=4)
        ctk.CTkButton(actions, text="Reset password", width=120, command=self._reset_password).pack(side="left", padx=4)

        self._refresh_users()

    def _refresh_users(self) -> None:
        self.user_tree.delete(*self.user_tree.get_children())
        for u in database.list_users():
            self.user_tree.insert("", "end", values=(u["id"], u["username"], u["full_name"] or "", u["role"]))

    def _selected_user(self) -> int | None:
        selection = self.user_tree.selection()
        if not selection:
            messagebox.showwarning("Users", "Select a user first")
            return None
        return int(self.user_tree.item(selection[0], "values")[0])

    def _add_user(self) -> None:
        username = self.u_username.get().strip()
        password = self.u_password.get()
        if not username or not password:
            messagebox.showerror("Add user", "Username and password are required")
            return
        try:
            database.create_user(
                username, password,
                full_name=self.u_fullname.get(), role=self.u_role.get(),
            )
        except Exception as exc:
            messagebox.showerror("Add user", f"Couldn't create user: {exc}")
            return
        self.u_username.set("")
        self.u_password.set("")
        self.u_fullname.set("")
        self._refresh_users()

    def _reset_password(self) -> None:
        user_id = self._selected_user()
        if user_id is None:
            return
        prompt = ctk.CTkInputDialog(text="New password:", title="Reset password")
        new_password = prompt.get_input()
        if not new_password:
            return
        try:
            database.update_user_password(user_id, new_password)
        except Exception as exc:
            messagebox.showerror("Reset password", str(exc))
            return
        messagebox.showinfo("Done", "Password updated.")

    def _change_role(self) -> None:
        user_id = self._selected_user()
        if user_id is None:
            return
        prompt = ctk.CTkInputDialog(text="New role (cashier/admin):", title="Change role")
        role = (prompt.get_input() or "").strip().lower()
        if role not in ("cashier", "admin"):
            messagebox.showerror("Change role", "Role must be 'cashier' or 'admin'")
            return
        try:
            database.update_user_role(user_id, role)
        except Exception as exc:
            messagebox.showerror("Change role", str(exc))
            return
        self._refresh_users()

    def _delete_user(self) -> None:
        user_id = self._selected_user()
        if user_id is None:
            return
        if not messagebox.askyesno("Delete user", "Remove this user account?"):
            return
        try:
            database.delete_user(user_id)
        except Exception as exc:
            messagebox.showerror("Delete user", str(exc))
            return
        self._refresh_users()
