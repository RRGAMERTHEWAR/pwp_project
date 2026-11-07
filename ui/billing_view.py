"""Billing form — CustomTkinter view.

This view handles the primary cashier workflow:
1. Customer Lookup: Searches by phone number to auto-fill customer name & loyalty points balance.
2. Line Items: Add products from the catalog (auto-populating unit prices and verifying available stock).
3. Live Totals: Calls `core.calculations` to calculate subtotal, tiered discounts, tax, and loyalty points.
4. Final Actions: Generates the bill, updates the SQLite database, deducts inventory stock, and previews the receipt.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from core.calculations import (
    Bill,
    LineItem,
    ValidationError,
    redemption_value,
    validate_amount,
    validate_int,
)
from db import database

if TYPE_CHECKING:  # pragma: no cover - for type hints only
    from ui.app import BillingApp


class BillingView(ctk.CTkFrame):
    """Main billing workspace where cashiers build orders and checkout customers."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp") -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self._item_rows: list[dict] = []
        self._products = database.list_products()
        self._customer: dict | None = None
        self._redeem_points = 0
        self._build()
        
        # ---------------- Keyboard Shortcuts (POS Hotkeys) ----------------
        # Cashiers can use function keys on physical keyboards for speed:
        # F1 = Add Item Row | F2 = Generate Bill | F3 = Recalculate Totals | F5 = Clear Form
        self.app.bind("<F1>", lambda e: self._add_item())
        self.app.bind("<F2>", lambda e: self._generate())
        self.app.bind("<F3>", lambda e: self._calculate())
        self.app.bind("<F5>", lambda e: self._clear())

    # -- layout ---------------------------------------------------------------

    def _build(self) -> None:
        """Assembles the UI sections vertically: Customer -> Items -> Totals -> Actions."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self._build_customer(self)
        self._build_items(self)
        self._build_totals(self)
        self._build_actions(self)

    def _build_customer(self, parent: ctk.CTkFrame) -> None:
        """Section 1: Customer Phone lookup, Name, Email, and Loyalty Points."""
        box = ctk.CTkFrame(parent, corner_radius=10)
        box.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        box.grid_columnconfigure(1, weight=1)
        box.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(box, text="Customer details", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=5, sticky="w", padx=12, pady=(10, 4)
        )

        ctk.CTkLabel(box, text="Phone:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        self.phone_var = ctk.StringVar()
        phone_entry = ctk.CTkEntry(box, textvariable=self.phone_var)
        phone_entry.grid(row=1, column=1, sticky="ew", padx=6, pady=4)
        phone_entry.bind("<FocusOut>", lambda _e: self._lookup_customer())
        phone_entry.bind("<Return>", lambda _e: self._lookup_customer())

        ctk.CTkButton(
            box, text="Lookup", width=80, command=self._lookup_customer
        ).grid(row=1, column=2, padx=(6, 12), pady=4)

        ctk.CTkLabel(box, text="Name *:").grid(row=1, column=3, sticky="w", pady=4)
        self.name_var = ctk.StringVar()
        ctk.CTkEntry(box, textvariable=self.name_var).grid(
            row=1, column=4, sticky="ew", padx=(6, 12), pady=4
        )

        ctk.CTkLabel(box, text="Email:").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        self.email_var = ctk.StringVar()
        ctk.CTkEntry(box, textvariable=self.email_var).grid(
            row=2, column=1, sticky="ew", padx=6, pady=4
        )

        self.balance_var = ctk.StringVar(value="Loyalty balance: —")
        ctk.CTkLabel(
            box, textvariable=self.balance_var, text_color="gray"
        ).grid(row=2, column=3, columnspan=2, sticky="w", padx=12, pady=4)

    def _build_items(self, parent: ctk.CTkFrame) -> None:
        box = ctk.CTkFrame(parent, corner_radius=10)
        box.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        box.grid_columnconfigure(0, weight=1)

        header = ctk.CTkFrame(box, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Line items", font=ctk.CTkFont(size=13, weight="bold")).grid(row=0, column=0, sticky="w")
        
        self.barcode_var = ctk.StringVar()
        barcode_entry = ctk.CTkEntry(header, textvariable=self.barcode_var, placeholder_text="Scan Barcode / ID", width=160)
        barcode_entry.grid(row=0, column=1, sticky="w", padx=16)
        barcode_entry.bind("<Return>", lambda e: self._handle_barcode())

        ctk.CTkButton(
            header, text="+ Add item", width=100, command=self._add_item
        ).grid(row=0, column=2, sticky="e")

        self.items_container = ctk.CTkScrollableFrame(box, label_text="", fg_color="transparent")
        self.items_container.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.items_container.grid_columnconfigure(0, weight=1)

        self._add_item()

    def _build_totals(self, parent: ctk.CTkFrame) -> None:
        box = ctk.CTkFrame(parent, corner_radius=10)
        box.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        box.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(box, text="Totals", font=ctk.CTkFont(size=13, weight="bold")).grid(
            row=0, column=0, columnspan=6, sticky="w", padx=12, pady=(10, 4)
        )

        self.subtotal_var = ctk.StringVar(value="0.00")
        self.discount_var = ctk.StringVar(value="0.00")
        self.redeem_var = ctk.StringVar(value="0.00")
        self.tax_var = ctk.StringVar(value="0.00")
        self.points_var = ctk.StringVar(value="0")
        self.total_var = ctk.StringVar(value="0.00")

        labels = [
            ("Subtotal:", self.subtotal_var),
            ("Discount:", self.discount_var),
            ("Points redeemed:", self.redeem_var),
        ]
        for col, (label, var) in enumerate(labels):
            ctk.CTkLabel(box, text=label).grid(
                row=1, column=col * 2, sticky="w", padx=(12, 2), pady=2
            )
            ctk.CTkLabel(box, textvariable=var, width=80, anchor="e").grid(
                row=1, column=col * 2 + 1, sticky="e", padx=(2, 12), pady=2
            )

        for col, (label, var) in enumerate(
            [("Tax:", self.tax_var), ("Points earned:", self.points_var)]
        ):
            ctk.CTkLabel(box, text=label).grid(
                row=2, column=col * 2, sticky="w", padx=(12, 2), pady=2
            )
            ctk.CTkLabel(box, textvariable=var, width=80, anchor="e").grid(
                row=2, column=col * 2 + 1, sticky="e", padx=(2, 12), pady=2
            )

        ctk.CTkLabel(
            box, text="TOTAL:", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=3, column=4, sticky="e", padx=(4, 2), pady=(4, 10))
        ctk.CTkLabel(
            box, textvariable=self.total_var, width=90, anchor="e",
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=3, column=5, sticky="e", padx=(2, 12), pady=(4, 10))

        # Loyalty & Promo coupon row
        redeem = ctk.CTkFrame(box, fg_color="transparent")
        redeem.grid(row=4, column=0, columnspan=6, sticky="ew", padx=12, pady=(0, 6))

        ctk.CTkLabel(redeem, text="Redeem points:").pack(side="left")
        self.redeem_entry = ctk.CTkEntry(redeem, width=70)
        self.redeem_entry.insert(0, "0")
        self.redeem_entry.pack(side="left", padx=4)
        ctk.CTkButton(redeem, text="Apply", width=60, command=self._apply_redemption).pack(side="left")
        self.redeem_status = ctk.StringVar(value="")
        ctk.CTkLabel(redeem, textvariable=self.redeem_status, text_color="gray").pack(
            side="left", padx=(4, 16)
        )

        ctk.CTkLabel(redeem, text="🎟️ Coupon:").pack(side="left")
        self.coupon_var = ctk.StringVar()
        self.coupon_entry = ctk.CTkEntry(redeem, textvariable=self.coupon_var, width=110, placeholder_text="e.g. WELCOME10")
        self.coupon_entry.pack(side="left", padx=4)
        ctk.CTkButton(redeem, text="Apply Code", width=85, command=self._apply_coupon).pack(side="left")
        self.coupon_status = ctk.StringVar(value="")
        ctk.CTkLabel(redeem, textvariable=self.coupon_status, text_color="#10b981", font=ctk.CTkFont(size=11, weight="bold")).pack(
            side="left", padx=6
        )

        # Cash Tendered & Change Due row
        tender_row = ctk.CTkFrame(box, fg_color=("#f1f5f9", "#1e293b"), corner_radius=8)
        tender_row.grid(row=5, column=0, columnspan=6, sticky="ew", padx=12, pady=(2, 10))

        ctk.CTkLabel(tender_row, text="💵 Cash Tendered:", font=ctk.CTkFont(size=12, weight="bold")).pack(side="left", padx=(10, 4), pady=6)
        self.tendered_var = ctk.StringVar()
        self.tendered_entry = ctk.CTkEntry(tender_row, textvariable=self.tendered_var, width=100, placeholder_text="0.00")
        self.tendered_entry.pack(side="left", padx=4, pady=6)
        self.tendered_entry.bind("<KeyRelease>", lambda _e: self._calc_change())

        # Quick tender shortcut buttons
        for amt in [100, 200, 500, 1000]:
            ctk.CTkButton(
                tender_row,
                text=f"+{amt}",
                width=45,
                height=26,
                corner_radius=6,
                fg_color=("#e2e8f0", "#334155"),
                text_color=("#1e293b", "#f8fafc"),
                hover_color=("#cbd5e1", "#475569"),
                font=ctk.CTkFont(size=11),
                command=lambda a=amt: self._quick_tender(a),
            ).pack(side="left", padx=2, pady=6)

        self.change_var = ctk.StringVar(value="Change Due: —")
        self.change_label = ctk.CTkLabel(
            tender_row,
            textvariable=self.change_var,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10b981",
        )
        self.change_label.pack(side="right", padx=14, pady=6)

    def _build_actions(self, parent: ctk.CTkFrame) -> None:
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=3, column=0, sticky="ew", padx=14, pady=(6, 14))

        ctk.CTkLabel(box, text="Payment Method:").pack(side="left", padx=(0, 8))
        self.payment_var = ctk.StringVar(value=self.app.settings.payment_methods[0] if self.app.settings.payment_methods else "Cash")
        ctk.CTkOptionMenu(
            box,
            variable=self.payment_var,
            values=self.app.settings.payment_methods or ["Cash"],
            width=120,
            corner_radius=8,
        ).pack(side="left")

        ctk.CTkButton(
            box,
            text="Clear (F5)",
            width=90,
            corner_radius=8,
            fg_color="#64748b",
            hover_color="#475569",
            command=self._clear,
        ).pack(side="left", padx=12)

        ctk.CTkButton(
            box,
            text="+ Add (F1)",
            width=90,
            corner_radius=8,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._add_item,
        ).pack(side="left")

        ctk.CTkButton(
            box,
            text="Generate Invoice (F2) ⚡",
            width=160,
            height=36,
            corner_radius=8,
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._generate,
        ).pack(side="right")

        ctk.CTkButton(
            box,
            text="Calculate (F3)",
            width=100,
            height=36,
            corner_radius=8,
            command=self._calculate,
        ).pack(side="right", padx=(0, 8))

    # -- item rows ------------------------------------------------------------

    def _product_names(self) -> list[str]:
        return [p["name"] for p in self._products]

    def _add_item(self) -> None:
        row = len(self._item_rows)
        frame = ctk.CTkFrame(self.items_container, fg_color="transparent")
        frame.grid(row=row, column=0, sticky="ew", pady=3)
        for col in range(5):
            frame.grid_columnconfigure(col, weight=0)
        frame.grid_columnconfigure(1, weight=1)

        product_var = ctk.StringVar(value="Select product…")
        qty_var = ctk.StringVar(value="1")
        price_var = ctk.StringVar(value="0.00")
        stock_var = ctk.StringVar(value="")

        ctk.CTkLabel(frame, text=f"#{row + 1}", width=26).grid(row=0, column=0, padx=(2, 6))

        combo = ctk.CTkComboBox(
            frame, values=self._product_names(), variable=product_var, width=210
        )
        combo.grid(row=0, column=1, sticky="ew", padx=4)
        combo.bind("<Return>", lambda _e, r=row: self._match_product(r))
        combo.bind("<FocusOut>", lambda _e, r=row: self._match_product(r))
        product_var.trace_add("write", lambda *a, r=row: self._on_product_typed(r))

        qty_entry = ctk.CTkEntry(frame, textvariable=qty_var, width=60)
        qty_entry.grid(row=0, column=2, padx=4)

        price_entry = ctk.CTkEntry(frame, textvariable=price_var, width=90)
        price_entry.grid(row=0, column=3, padx=4)

        ctk.CTkLabel(frame, textvariable=stock_var, width=70, text_color="gray").grid(
            row=0, column=4, padx=4
        )

        ctk.CTkButton(
            frame, text="✕", width=28, fg_color="transparent",
            hover_color="#e74c3c", command=lambda: self._remove_item(row),
        ).grid(row=0, column=5, padx=(4, 2))

        self._item_rows.append(
            {
                "frame": frame,
                "product": product_var,
                "qty": qty_var,
                "price": price_var,
                "stock": stock_var,
                "product_id": None,
            }
        )

    def _remove_item(self, row_idx: int) -> None:
        if len(self._item_rows) <= 1:
            r = self._item_rows[0]
            r["product"].set("Select product…")
            r["qty"].set("1")
            r["price"].set("0.00")
            r["stock"].set("")
            r["product_id"] = None
            return
        rec = self._item_rows.pop(row_idx)
        rec["frame"].destroy()
        for i, r in enumerate(self._item_rows):
            r["frame"].grid(row=i, column=0, sticky="ew", pady=3)
            r["frame"].grid_columnconfigure(1, weight=1)

    # -- product matching -----------------------------------------------------

    def _on_product_typed(self, row_idx: int) -> None:
        if row_idx >= len(self._item_rows):
            return
        r = self._item_rows[row_idx]
        text = r["product"].get().strip()
        product = next((p for p in self._products if p["name"].lower() == text.lower()), None)
        if product is not None:
            r["product_id"] = product["id"]
            r["price"].set(f"{product['price']:.2f}")
            r["stock"].set(f"stock: {product['stock']}")
        else:
            r["product_id"] = None
            r["stock"].set("")

    def _match_product(self, row_idx: int) -> None:
        """Re-resolve a row's product after the combobox is typed/left."""
        self._on_product_typed(row_idx)

    def _handle_barcode(self) -> None:
        code = self.barcode_var.get().strip().lower()
        self.barcode_var.set("")
        if not code: return
        
        product = next((p for p in self._products if code in p["name"].lower() or str(p["id"]) == code), None)
        if product:
            for r in self._item_rows:
                if r["product_id"] == product["id"]:
                    qty = int(r["qty"].get() or 0)
                    r["qty"].set(str(qty + 1))
                    return
            # Not in list, add new row if current empty or append
            if len(self._item_rows) == 1 and not self._item_rows[0]["product_id"]:
                r = self._item_rows[0]
            else:
                self._add_item()
                r = self._item_rows[-1]
            r["product"].set(product["name"])
            self._on_product_typed(len(self._item_rows)-1)

    # -- customer lookup ------------------------------------------------------

    def _lookup_customer(self) -> None:
        phone = self.phone_var.get().strip()
        if not phone:
            return
        customer = database.find_customer_by_phone(phone)
        if customer is None:
            self._customer = None
            self.balance_var.set("No customer found with this phone")
            return
        self._customer = customer
        self.name_var.set(customer["name"])
        self.email_var.set(customer.get("email") or "")
        self.balance_var.set(f"Loyalty balance: {customer['loyalty_balance']} pts")

    # -- redemption -----------------------------------------------------------

    def _apply_redemption(self) -> None:
        try:
            points = validate_int(self.redeem_entry.get(), field="points to redeem")
        except ValidationError as exc:
            from tkinter import messagebox

            messagebox.showerror("Invalid input", str(exc))
            return
        if self._customer is not None:
            available = self._customer.get("loyalty_balance", 0)
            if points > available:
                from tkinter import messagebox

                messagebox.showwarning(
                    "Loyalty redemption",
                    f"Customer only has {available} points. Capping redemption at {available}.",
                )
                points = available
        self._redeem_points = points
        self.redeem_status.set(
            f"Applied {points} pts → "
            f"{self.app.settings.currency}{redemption_value(points, settings=self.app.settings):.2f} off"
        )

    # -- collect + calculate --------------------------------------------------

    def _collect_items(self) -> list[LineItem]:
        items: list[LineItem] = []
        for r in self._item_rows:
            desc = r["product"].get().strip()
            if not desc or desc == "Select product…":
                continue
            qty = validate_int(r["qty"].get(), field="quantity")
            price = validate_amount(r["price"].get(), field="unit price")
            product_id = r["product_id"]
            unit_cost = 0.0
            if product_id:
                product = next((p for p in self._products if p["id"] == product_id), None)
                if product:
                    unit_cost = product.get("cost_price", 0.0)
            items.append(LineItem(desc, qty, price, product_id=product_id, unit_cost=unit_cost))
        return items

    def _customer_dict(self) -> dict:
        if self._customer is not None:
            return self._customer
        return {
            "id": None,
            "name": self.name_var.get(),
            "phone": self.phone_var.get(),
            "email": self.email_var.get(),
        }

    def _calculate(self) -> Bill | None:
        try:
            items = self._collect_items()
            customer = self._customer_dict()
            max_points = (
                customer.get("loyalty_balance", 0) if customer.get("id") else 0
            )
            bill = Bill.from_items(
                customer=customer,
                items=items,
                settings=self.app.settings,
                points_used=self._redeem_points,
                max_points=max_points,
                payment_method=self.payment_var.get(),
                coupon_code=getattr(self, "coupon_var", ctk.StringVar()).get().strip(),
            )
        except ValidationError as exc:
            from tkinter import messagebox

            messagebox.showerror("Invalid input", str(exc))
            return None
        self._render_totals(bill)
        self._last_bill = bill
        return bill

    def _apply_coupon(self) -> None:
        """Validate and apply promo discount code."""
        code = self.coupon_var.get().strip().upper()
        if not code:
            self.coupon_status.set("")
            self._calculate()
            return

        coupons = getattr(self.app.settings, "coupons", {})
        if code in coupons:
            pct = coupons[code]
            self.coupon_status.set(f"✓ Applied ({pct}% OFF)")
            self.app.notify(f"Coupon '{code}' applied: {pct}% off!", kind="success")
            self._calculate()
        else:
            self.coupon_status.set("✕ Invalid code")
            self.app.notify("Invalid promo coupon code", kind="error")

    def _render_totals(self, bill: Bill) -> None:
        self.subtotal_var.set(f"{bill.subtotal:.2f}")
        self.discount_var.set(f"{bill.discount:.2f}")
        self.redeem_var.set(f"{bill.points_redeemed:.2f}")
        self.tax_var.set(f"{bill.tax:.2f}")
        self.points_var.set(str(bill.loyalty_points))
        self.total_var.set(f"{bill.total:.2f}")
        self._calc_change()

    def _calc_change(self) -> None:
        """Calculate and display change due based on cash tendered vs bill total."""
        currency = self.app.settings.currency
        try:
            total = float(self.total_var.get())
        except (ValueError, TypeError):
            total = 0.0

        raw_tendered = self.tendered_var.get().strip()
        if not raw_tendered:
            self.change_var.set("Change Due: —")
            self.change_label.configure(text_color="#10b981")
            return

        try:
            tendered = float(raw_tendered)
            diff = tendered - total
            if diff >= 0:
                self.change_var.set(f"Change Due: {currency}{diff:,.2f}")
                self.change_label.configure(text_color="#10b981")
            else:
                self.change_var.set(f"Due Balance: {currency}{abs(diff):,.2f}")
                self.change_label.configure(text_color="#ef4444")
        except ValueError:
            self.change_var.set("Change: Invalid amount")
            self.change_label.configure(text_color="#ef4444")

    def _quick_tender(self, add_amount: float) -> None:
        """Increment the cash tendered by a preset button amount."""
        try:
            current = float(self.tendered_var.get() or "0")
        except ValueError:
            current = 0.0
        new_val = current + add_amount
        self.tendered_var.set(f"{new_val:.2f}")
        self._calc_change()

    def _clear(self) -> None:
        from datetime import datetime

        self.name_var.set("")
        self.phone_var.set("")
        self.email_var.set("")
        self._customer = None
        self._redeem_points = 0
        self.redeem_entry.delete(0, "end")
        self.redeem_entry.insert(0, "0")
        self.redeem_status.set("")
        self.balance_var.set("Loyalty balance: —")
        self.tendered_var.set("")
        self.change_var.set("Change Due: —")
        for r in self._item_rows[1:]:
            r["frame"].destroy()
        self._item_rows = []
        self._add_item()
        self._last_bill = None
        self._render_totals(
            Bill(
                customer_id=None, customer_name="", customer_phone="",
                customer_email="", items=[], subtotal=0.0, discount=0.0,
                points_used=0, points_redeemed=0.0, tax=0.0,
                loyalty_points=0, total=0.0, created_at=datetime.now(),
            )
        )

    # -- generate bill --------------------------------------------------------

    def _generate(self) -> None:
        from tkinter import messagebox

        bill = self._calculate()
        if bill is None:
            return
        if not bill.customer_name:
            messagebox.showerror("Invalid input", "Customer name is required")
            return
        if not bill.items:
            messagebox.showerror("Invalid input", "Add at least one line item")
            return
        shortages = database.check_stock(bill.items)
        if shortages:
            details = ", ".join(f"{name} (only {qty} left)" for name, qty in shortages.items())
            messagebox.showerror(
                "Insufficient stock",
                f"Not enough stock for:\n{details}\n\nReduce the quantity or restock first.",
            )
            return
        self.app.show_receipt(bill)
