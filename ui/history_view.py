"""Searchable Bill History View.

Provides an audit log and search tool for all past transactions:
- Filters bills by date range (From/To), customer name, or customer phone.
- Displays line-item breakdowns of individual historical receipts.
- Exports records to CSV (bill summary or item-by-item) and formatted PDF.
"""

from __future__ import annotations

import csv
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.calculations import format_receipt
from core.pdfexport import export_history_pdf
from db import database

if TYPE_CHECKING:  # pragma: no cover
    from ui.app import BillingApp


class HistoryView(ctk.CTkFrame):
    """Table of saved bills filterable by date range, name or phone."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp") -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self._rows: list[dict] = []
        self._build()
        self._search()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ctk.CTkLabel(
            header, text="Bill History", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        filters = ctk.CTkFrame(self, corner_radius=10)
        filters.grid(row=1, column=0, sticky="ew", padx=14, pady=6)
        filters.grid_columnconfigure(4, weight=1)

        ctk.CTkLabel(filters, text="From:").grid(row=0, column=0, padx=(12, 4), pady=8)
        self.from_var = ctk.StringVar()
        ctk.CTkEntry(filters, textvariable=self.from_var, width=100,
                     placeholder_text="YYYY-MM-DD").grid(row=0, column=1, padx=4, pady=8)
        ctk.CTkLabel(filters, text="To:").grid(row=0, column=2, padx=(8, 4), pady=8)
        self.to_var = ctk.StringVar()
        ctk.CTkEntry(filters, textvariable=self.to_var, width=100,
                     placeholder_text="YYYY-MM-DD").grid(row=0, column=3, padx=4, pady=8)

        ctk.CTkLabel(filters, text="Customer:").grid(row=1, column=0, padx=(12, 4), pady=8)
        self.name_var = ctk.StringVar()
        ctk.CTkEntry(filters, textvariable=self.name_var, width=140).grid(row=1, column=1, padx=4, pady=8)
        ctk.CTkLabel(filters, text="Phone:").grid(row=1, column=2, padx=(8, 4), pady=8)
        self.phone_var = ctk.StringVar()
        ctk.CTkEntry(filters, textvariable=self.phone_var, width=120).grid(row=1, column=3, padx=4, pady=8)

        btns = ctk.CTkFrame(filters, fg_color="transparent")
        btns.grid(row=0, column=4, rowspan=2, sticky="e", padx=12)
        ctk.CTkButton(btns, text="Search", width=90, command=self._search).pack(side="right", padx=4)
        ctk.CTkButton(btns, text="Clear", width=80, fg_color="#6c757d",
                      command=self._clear_filters).pack(side="right", padx=4)

        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=6)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame,
            columns=("id", "date", "customer", "phone", "points", "total"),
            show="headings", selectmode="browse",
        )
        headings = {
            "id": "ID", "date": "Date", "customer": "Customer",
            "phone": "Phone", "points": "Pts", "total": "Total",
        }
        for col, text in headings.items():
            self.tree.heading(col, text=text)
        self.tree.column("id", width=60, stretch=False)
        self.tree.column("date", width=150, stretch=False)
        self.tree.column("customer", width=220)
        self.tree.column("phone", width=120)
        self.tree.column("points", width=60, anchor="e")
        self.tree.column("total", width=100, anchor="e")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        yscroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.tree.bind("<Double-1>", self._show_receipt)

        self.summary_var = ctk.StringVar()
        ctk.CTkLabel(self, textvariable=self.summary_var, text_color="gray").grid(
            row=3, column=0, sticky="w", padx=14, pady=2
        )

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, sticky="ew", padx=14, pady=(6, 14))
        ctk.CTkButton(
            actions,
            text="📄 View Receipt",
            width=120,
            height=34,
            corner_radius=8,
            command=self._show_receipt,
        ).pack(side="left")
        ctk.CTkButton(
            actions,
            text="🔄 Return / Refund",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            command=self._refund_selected,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            actions,
            text="Export PDF",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._export_pdf,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions,
            text="Export CSV (Items)",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            command=self._export_csv_items,
        ).pack(side="right", padx=(8, 0))
        ctk.CTkButton(
            actions,
            text="Export CSV (Bills)",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            command=self._export_csv_bills,
        ).pack(side="right")

    def _refund_selected(self) -> None:
        """Process refund on the selected bill and restore stock."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Return / Refund", "Please select a bill from the table first.")
            return
        item_vals = self.tree.item(selection[0], "values")
        bill_id = int(item_vals[0])

        if not messagebox.askyesno(
            "Confirm Return / Refund",
            f"Are you sure you want to process a full return/refund for Bill #{bill_id}?\n\n"
            "This will restock all purchased products and adjust customer loyalty points.",
        ):
            return

        success, msg = database.refund_bill(bill_id)
        if success:
            self.app.notify(msg, kind="success")
            self._search()
            self.app.refresh_low_stock_badge()
        else:
            messagebox.showerror("Refund Failed", msg)

    # -- actions --------------------------------------------------------------

    def _search(self) -> None:
        self._rows = database.search_bills(
            from_date=self.from_var.get().strip(),
            to_date=self.to_var.get().strip(),
            customer_name=self.name_var.get(),
            phone=self.phone_var.get(),
        )
        self.tree.delete(*self.tree.get_children())
        currency = self.app.settings.currency
        for r in self._rows:
            self.tree.insert(
                "", "end",
                values=(
                    r["id"], str(r["created_at"])[:19], r["customer_name"],
                    r["phone"] or "", r["loyalty_points"],
                    f"{currency}{r['total']:.2f}",
                ),
            )
        total = sum(r["total"] for r in self._rows)
        self.summary_var.set(
            f"{len(self._rows)} bills  ·  total revenue {currency}{total:.2f}"
        )

    def _clear_filters(self) -> None:
        self.from_var.set("")
        self.to_var.set("")
        self.name_var.set("")
        self.phone_var.set("")
        self._search()

    def _show_receipt(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        bill_id = int(self.tree.item(selection[0], "values")[0])
        record = database.get_bill(bill_id)
        if record is None:
            messagebox.showerror("Not found", f"Bill #{bill_id} no longer exists")
            return
        items = database.get_bill_items(bill_id)
        bill = database.bill_to_receipt(record, items)
        body = format_receipt(bill, settings=self.app.settings)

        win = ctk.CTkToplevel(self)
        win.title(f"Bill #{bill_id}")
        win.geometry("560x480")
        text = tk.Text(win, font=("Consolas", 10), wrap="none",
                       bg="#1a1a1a" if ctk.get_appearance_mode() == "Dark" else "#ffffff",
                       fg="#f0f0f0" if ctk.get_appearance_mode() == "Dark" else "#111111",
                       relief="flat", highlightthickness=0)
        yscroll = ttk.Scrollbar(win, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=yscroll.set)
        text.pack(side="left", fill="both", expand=True, padx=(10, 0), pady=10)
        yscroll.pack(side="right", fill="y", padx=(0, 10), pady=10)
        text.insert("1.0", body)
        text.configure(state="disabled")

    def _export_csv_bills(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Export bills as CSV", defaultextension=".csv",
            initialfile="bill_history.csv", filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        try:
            self._write_csv_bills(path)
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Exported", f"Saved {len(self._rows)} bills to:\n{path}")

    def _write_csv_bills(self, path: str) -> None:
        currency = self.app.settings.currency
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow(
                ["Bill ID", "Date", "Customer", "Phone", "Subtotal", "Discount",
                 "Tax", "Points", "Total", "Currency"]
            )
            for r in self._rows:
                writer.writerow(
                    [r["id"], str(r["created_at"])[:19], r["customer_name"],
                     r["phone"] or "", f"{r['subtotal']:.2f}",
                     f"{r['discount']:.2f}", f"{r['tax']:.2f}",
                     r["loyalty_points"], f"{r['total']:.2f}", currency]
                )

    def _export_csv_items(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Export line items as CSV", defaultextension=".csv",
            initialfile="bill_items.csv", filetypes=[("CSV files", "*.csv")],
        )
        if not path:
            return
        rows = database.flatten_bill_items()
        try:
            with open(path, "w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.writer(fh)
                writer.writerow(
                    ["Bill ID", "Date", "Customer", "Phone", "Description",
                     "Qty", "Unit Price", "Line Total", "Bill Total", "Currency"]
                )
                currency = self.app.settings.currency
                for r in rows:
                    writer.writerow(
                        [r["bill_id"], str(r["created_at"])[:19], r["customer_name"],
                         r["phone"] or "", r["description"], r["qty"],
                         f"{r['unit_price']:.2f}", f"{r['line_total']:.2f}",
                         f"{r['bill_total']:.2f}", currency]
                    )
        except OSError as exc:
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Exported", f"Saved {len(rows)} line items to:\n{path}")

    def _export_pdf(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Export bill history as PDF", defaultextension=".pdf",
            initialfile="bill_history.pdf", filetypes=[("PDF files", "*.pdf")],
        )
        if not path:
            return
        try:
            export_history_pdf(self._rows, path, self.app.settings)
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror("Export failed", str(exc))
            return
        messagebox.showinfo("Exported", f"Saved {len(self._rows)} bills to:\n{path}")
