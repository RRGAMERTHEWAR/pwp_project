"""Sales Dashboard & Analytics View (Admin Only).

Renders financial charts and metrics using `matplotlib`:
- Key performance metric cards (Today's revenue, this week, this month, total orders).
- 30-day daily sales revenue line/bar chart.
- Top-selling products bar chart and top loyal customer rankings.
- Sales report CSV export.
"""

from __future__ import annotations

import csv
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING
from datetime import datetime

import customtkinter as ctk
import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from db import database

if TYPE_CHECKING:  # pragma: no cover
    from ui.app import BillingApp


class AnalyticsView(ctk.CTkFrame):
    """Revenue summary + bar charts for items and customers."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp") -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self._build()
        self.refresh()

    def _colors(self) -> tuple[str, str, str]:
        if ctk.get_appearance_mode() == "Dark":
            return "#2b2b2b", "#f0f0f0", "#4fa3e3"
        return "#f5f5f5", "#222222", "#2563eb"

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ctk.CTkLabel(
            header, text="Sales Dashboard", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        self.start_date = ctk.StringVar()
        self.end_date = ctk.StringVar()
        
        date_frame = ctk.CTkFrame(header, fg_color="transparent")
        date_frame.pack(side="right")
        
        ctk.CTkLabel(date_frame, text="From:").pack(side="left", padx=2)
        ctk.CTkEntry(date_frame, textvariable=self.start_date, width=90, placeholder_text="YYYY-MM-DD").pack(side="left", padx=2)
        ctk.CTkLabel(date_frame, text="To:").pack(side="left", padx=2)
        ctk.CTkEntry(date_frame, textvariable=self.end_date, width=90, placeholder_text="YYYY-MM-DD").pack(side="left", padx=2)
        ctk.CTkButton(date_frame, text="Apply", width=60, command=self.refresh).pack(side="left", padx=4)
        ctk.CTkButton(date_frame, text="📊 Daily Z-Report", width=120, fg_color="#8b5cf6", hover_color="#7c3aed", command=self._show_z_report).pack(side="left", padx=4)
        ctk.CTkButton(date_frame, text="Export CSV", width=80, fg_color="#27ae60", hover_color="#2ecc71", command=self._export_csv).pack(side="left", padx=4)

        # Key Metric Cards
        self.cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.cards_frame.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        for col in range(4):
            self.cards_frame.grid_columnconfigure(col, weight=1)

        self.revenue_card_val = ctk.StringVar(value="—")
        self.profit_card_val = ctk.StringVar(value="—")
        self.margin_card_val = ctk.StringVar(value="—")
        self.volume_card_val = ctk.StringVar(value="—")

        cards_data = [
            ("Total Revenue", self.revenue_card_val, "#3b82f6"),
            ("Gross Profit", self.profit_card_val, "#10b981"),
            ("Profit Margin", self.margin_card_val, "#8b5cf6"),
            ("Orders / Volume", self.volume_card_val, "#f59e0b"),
        ]

        for i, (title, var, color) in enumerate(cards_data):
            card = ctk.CTkFrame(self.cards_frame, corner_radius=10, fg_color=("#ffffff", "#1e293b"))
            card.grid(row=0, column=i, sticky="nsew", padx=4 if i > 0 else (0, 4))
            ctk.CTkLabel(card, text=title, font=ctk.CTkFont(size=11, weight="bold"), text_color="gray").pack(anchor="w", padx=12, pady=(10, 2))
            ctk.CTkLabel(card, textvariable=var, font=ctk.CTkFont(size=16, weight="bold"), text_color=color).pack(anchor="w", padx=12, pady=(0, 10))

        self.body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.body.grid(row=2, column=0, sticky="nsew", padx=14, pady=(0, 14))
        self.body.grid_columnconfigure(0, weight=1)

        self._figures: list[Figure] = []

    def _make_figure(self, title: str, height: float = 2.9) -> Figure:
        fig = Figure(figsize=(7.2, height), dpi=90)
        face, text, bar = self._colors()
        fig.patch.set_facecolor(face)
        return fig

    def _style_axis(self, ax, face: str, text: str) -> None:
        ax.set_facecolor(face)
        ax.tick_params(colors=text, labelsize=8)
        for spine in ax.spines.values():
            spine.set_color(text)
        ax.xaxis.label.set_color(text)
        ax.yaxis.label.set_color(text)

    def _build_charts(self, start: str, end: str) -> None:
        currency = self.app.settings.currency
        face, text, bar = self._colors()

        # Payment Methods (Pie Chart)
        payments = database.revenue_by_payment_method(start, end)
        if payments:
            fig = self._make_figure("")
            ax = fig.add_subplot(111)
            self._style_axis(ax, face, text)
            labels = [r["payment_method"] for r in payments]
            sizes = [r["total"] for r in payments]
            ax.pie(sizes, labels=labels, autopct='%1.1f%%', textprops={'color': text})
            ax.set_title("Revenue by Payment Method", color=text, fontsize=10)
            self._attach(fig)
            
        # Cashier Performance (Bar Chart)
        cashiers = database.cashier_performance(start, end)
        if cashiers:
            fig = self._make_figure("")
            ax = fig.add_subplot(111)
            self._style_axis(ax, face, text)
            names = [r["full_name"] or r["username"] for r in cashiers][::-1]
            revenues = [r["revenue"] for r in cashiers][::-1]
            ax.barh(names, revenues, color=bar)
            ax.set_title("Top Cashiers (by revenue)", color=text, fontsize=10)
            ax.set_xlabel(f"Revenue ({currency})", color=text, fontsize=8)
            self._attach(fig)

        # Top items
        fig = self._make_figure("")
        ax = fig.add_subplot(111)
        self._style_axis(ax, face, text)
        items = database.top_items(5)
        names = [r["description"][:22] for r in items][::-1]
        qtys = [r["qty"] for r in items][::-1]
        ax.barh(names, qtys, color=bar)
        ax.set_title("Top-selling items (by quantity)", color=text, fontsize=10)
        ax.set_xlabel("Quantity sold", color=text, fontsize=8)
        self._attach(fig)

        # Top customers
        fig = self._make_figure("")
        ax = fig.add_subplot(111)
        self._style_axis(ax, face, text)
        customers = database.top_customers(5)
        names = [r["customer_name"][:22] for r in customers][::-1]
        revenues = [r["revenue"] for r in customers][::-1]
        ax.barh(names, revenues, color=bar)
        ax.set_title("Top customers (by revenue)", color=text, fontsize=10)
        ax.set_xlabel(f"Revenue ({currency})", color=text, fontsize=8)
        self._attach(fig)

    def _attach(self, fig: Figure) -> None:
        canvas = FigureCanvasTkAgg(fig, master=self.body)
        canvas.get_tk_widget().grid(row=len(self._figures), column=0, sticky="ew", pady=8)
        self._figures.append(fig)

    def refresh(self) -> None:
        currency = self.app.settings.currency
        start = self.start_date.get().strip()
        end = self.end_date.get().strip()
        
        try:
            revenue, count, sold = database.revenue_for_period_custom(start, end)
            rev, cost, profit = database.profit_margins(start, end)
        except Exception:
            revenue, count, sold, profit = 0.0, 0, 0, 0.0
            rev, cost = 0.0, 0.0

        margin_pct = (profit / revenue * 100.0) if revenue > 0 else 0.0

        self.revenue_card_val.set(f"{currency}{revenue:,.2f}")
        self.profit_card_val.set(f"{currency}{profit:,.2f}")
        self.margin_card_val.set(f"{margin_pct:.1f}%")
        self.volume_card_val.set(f"{count} bills ({sold} items)")

        for child in self.body.winfo_children():
            child.destroy()
        self._figures = []
        self._build_charts(start, end)

    def _export_csv(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self, title="Export Analytics to CSV", defaultextension=".csv",
            initialfile=f"analytics_export_{datetime.now():%Y%m%d}.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        
        try:
            bills = database.search_bills(from_date=self.start_date.get().strip(), to_date=self.end_date.get().strip())
            with open(path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Bill ID", "Date", "Customer", "Total", "Payment Method"])
                for b in bills:
                    writer.writerow([b["id"], b["created_at"], b["customer_name"], b["total"], b["payment_method"]])
            messagebox.showinfo("Export Successful", f"Data exported successfully to:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export Failed", f"Could not export data:\n{exc}")

    def _show_z_report(self) -> None:
        """Display an end-of-day register closure Z-Report."""
        today = datetime.now().strftime("%Y-%m-%d")
        currency = self.app.settings.currency

        revenue, count, sold = database.revenue_for_period_custom(today, today)
        payments = database.revenue_by_payment_method(today, today)

        win = ctk.CTkToplevel(self)
        win.title(f"Daily Closing Z-Report — {today}")
        win.geometry("420x500")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(
            win,
            text="📑 End-of-Day Z-Report",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).pack(pady=(20, 4))
        ctk.CTkLabel(
            win,
            text=f"Store: {self.app.settings.store_name}  |  Date: {today}",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        ).pack(pady=(0, 16))

        card = ctk.CTkFrame(win, corner_radius=10)
        card.pack(fill="x", padx=24, pady=6)

        stats = [
            ("Total Invoices Issued:", str(count)),
            ("Total Items Sold:", str(sold)),
            ("Gross Revenue:", f"{currency}{revenue:,.2f}"),
        ]
        for row_i, (lbl, val) in enumerate(stats):
            ctk.CTkLabel(card, text=lbl, font=ctk.CTkFont(size=12)).grid(row=row_i, column=0, sticky="w", padx=14, pady=6)
            ctk.CTkLabel(card, text=val, font=ctk.CTkFont(size=12, weight="bold")).grid(row=row_i, column=1, sticky="e", padx=14, pady=6)
        card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(win, text="Payment Breakdown", font=ctk.CTkFont(size=13, weight="bold"), anchor="w").pack(fill="x", padx=26, pady=(12, 4))
        pay_card = ctk.CTkFrame(win, corner_radius=10)
        pay_card.pack(fill="x", padx=24, pady=4)
        pay_card.grid_columnconfigure(0, weight=1)

        if not payments:
            ctk.CTkLabel(pay_card, text="No transactions recorded today", text_color="gray").pack(pady=10)
        else:
            for p_idx, p in enumerate(payments):
                ctk.CTkLabel(pay_card, text=f"{p['payment_method']} ({p['count']} txns):").grid(row=p_idx, column=0, sticky="w", padx=14, pady=4)
                ctk.CTkLabel(pay_card, text=f"{currency}{p['total']:,.2f}", font=ctk.CTkFont(weight="bold")).grid(row=p_idx, column=1, sticky="e", padx=14, pady=4)

        ctk.CTkButton(
            win,
            text="Close Register Report",
            width=160,
            height=34,
            corner_radius=8,
            command=win.destroy,
        ).pack(pady=(20, 10))
