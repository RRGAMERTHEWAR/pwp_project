"""Inventory & Product Management Screen (Admin Only).

Allows store administrators to:
- View all catalog items in a searchable table.
- Add new products, update prices, and adjust stock quantities.
- Generate barcode price tags and import/export product lists to CSV.
"""

from __future__ import annotations

import csv  
import os
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.calculations import ValidationError, validate_amount, validate_int
from db import database

if TYPE_CHECKING:  # pragma: no cover
    from ui.app import BillingApp


class ProductView(ctk.CTkFrame):
    """CRUD (Create, Read, Update, Delete) interface for store inventory."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp") -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self._build()
        self._refresh()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        ctk.CTkLabel(
            header, text="Inventory & Products", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")

        self.search_entry = ctk.CTkEntry(header, width=180, placeholder_text="Search products…")
        self.search_entry.pack(side="right", padx=(6, 0))
        self.search_entry.bind("<KeyRelease>", lambda _e: self._refresh())

        ctk.CTkButton(
            header,
            text="🏷️ Barcode Tag",
            width=115,
            height=32,
            corner_radius=8,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            command=self._generate_barcode_tag,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            header,
            text="📥 Import CSV",
            width=100,
            height=32,
            corner_radius=8,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._import_csv,
        ).pack(side="right", padx=4)

        ctk.CTkButton(
            header,
            text="📤 Export CSV",
            width=100,
            height=32,
            corner_radius=8,
            fg_color="#475569",
            hover_color="#334155",
            command=self._export_csv,
        ).pack(side="right", padx=4)

        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame, columns=("id", "name", "price", "cost_price", "stock"),
            show="headings", selectmode="browse",
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Name")
        self.tree.heading("price", text="Price")
        self.tree.heading("cost_price", text="Cost")
        self.tree.heading("stock", text="Stock")
        self.tree.column("id", width=50, stretch=False)
        self.tree.column("name", width=300)
        self.tree.column("price", width=80, anchor="e")
        self.tree.column("cost_price", width=80, anchor="e")
        self.tree.column("stock", width=80, anchor="e")
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        yscroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        # Form
        form = ctk.CTkFrame(self, corner_radius=10)
        form.grid(row=2, column=0, sticky="ew", padx=14, pady=6)
        form.grid_columnconfigure(1, weight=2)
        form.grid_columnconfigure(3, weight=1)
        form.grid_columnconfigure(5, weight=1)
        form.grid_columnconfigure(7, weight=1)

        self.name_var = ctk.StringVar()
        self.price_var = ctk.StringVar()
        self.cost_var = ctk.StringVar()
        self.stock_var = ctk.StringVar()

        ctk.CTkLabel(form, text="Product Name:").grid(row=0, column=0, sticky="w", padx=(14, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.name_var, placeholder_text="e.g. Arabica Coffee Beans").grid(row=0, column=1, sticky="ew", padx=4, pady=12)

        ctk.CTkLabel(form, text="Sale Price:").grid(row=0, column=2, sticky="w", padx=(12, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.price_var, placeholder_text="0.00").grid(row=0, column=3, sticky="ew", padx=4, pady=12)

        ctk.CTkLabel(form, text="Cost Price:").grid(row=0, column=4, sticky="w", padx=(12, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.cost_var, placeholder_text="0.00").grid(row=0, column=5, sticky="ew", padx=4, pady=12)

        ctk.CTkLabel(form, text="Stock:").grid(row=0, column=6, sticky="w", padx=(12, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.stock_var, placeholder_text="0").grid(row=0, column=7, sticky="ew", padx=(4, 14), pady=12)

        buttons = ctk.CTkFrame(self, fg_color="transparent")
        buttons.grid(row=3, column=0, sticky="ew", padx=14, pady=(4, 14))
        ctk.CTkButton(
            buttons,
            text="+ Add Product",
            width=120,
            height=34,
            corner_radius=8,
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            font=ctk.CTkFont(weight="bold"),
            command=self._add,
        ).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Update Selected",
            width=130,
            height=34,
            corner_radius=8,
            command=self._update,
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            buttons,
            text="Delete",
            width=90,
            height=34,
            corner_radius=8,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            command=self._delete,
        ).pack(side="left")
        ctk.CTkButton(
            buttons,
            text="Clear Form",
            width=100,
            height=34,
            corner_radius=8,
            fg_color="#64748b",
            hover_color="#475569",
            command=self._clear_form,
        ).pack(side="right")

    # -- helpers --------------------------------------------------------------

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        products = database.list_products()
        query = self.search_entry.get().strip().lower()
        currency = self.app.settings.currency

        self.tree.tag_configure("low_stock", foreground="#e74c3c")

        for p in products:
            if query and query not in p["name"].lower():
                continue
            tags = ()
            # Use database-defined min_stock if available, otherwise default to 5
            min_s = p.get("min_stock", 5)
            if p["stock"] <= min_s:
                tags = ("low_stock",)
            self.tree.insert(
                "", "end",
                values=(p["id"], p["name"], f"{currency}{p['price']:.2f}", f"{currency}{p.get('cost_price', 0):.2f}", p["stock"]),
                tags=tags,
            )

    def _on_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        self._selected_id = int(values[0])
        self.name_var.set(values[1])
        self.price_var.set(str(float(str(values[2]).replace(self.app.settings.currency, ""))))
        self.cost_var.set(str(float(str(values[3]).replace(self.app.settings.currency, ""))))
        self.stock_var.set(str(values[4]))

    def _form_data(self) -> tuple[str, float, int, float]:
        name = self.name_var.get().strip()
        if not name:
            raise ValidationError("Product name is required")
        price = validate_amount(self.price_var.get(), field="price")
        cost = validate_amount(self.cost_var.get(), field="cost")
        stock = validate_int(self.stock_var.get(), field="stock")
        return name, price, stock, cost

    def _clear_form(self) -> None:
        self._selected_id = None
        self.name_var.set("")
        self.price_var.set("")
        self.cost_var.set("")
        self.stock_var.set("")
        self.tree.selection_remove(*self.tree.selection())

    # -- actions --------------------------------------------------------------

    def _add(self) -> None:
        try:
            name, price, stock, cost = self._form_data()
            database.add_product(name, price, stock, cost)
        except (ValidationError, ValueError) as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self._clear_form()
        self._refresh()
        self.app.refresh_low_stock_badge()
        self.app.notify(f"Added '{name}' to inventory")

    def _update(self) -> None:
        product_id = getattr(self, "_selected_id", None)
        if product_id is None:
            messagebox.showwarning("Update", "Select a product first")
            return
        try:
            name, price, stock, cost = self._form_data()
            database.update_product(product_id, name, price, stock, cost)
        except (ValidationError, ValueError) as exc:
            messagebox.showerror("Invalid input", str(exc))
            return
        self._clear_form()
        self._refresh()
        self.app.refresh_low_stock_badge()
        self.app.notify(f"Updated '{name}'")

    def _delete(self) -> None:
        product_id = getattr(self, "_selected_id", None)
        if product_id is None:
            messagebox.showwarning("Delete", "Select a product first")
            return
        if not messagebox.askyesno("Delete product", "Delete this product from the catalogue?"):
            return
        database.delete_product(product_id)
        self._clear_form()
        self._refresh()
        self.app.refresh_low_stock_badge()
        self.app.notify("Product removed from catalogue")

    def _export_csv(self) -> None:
        """Export full inventory to a CSV spreadsheet."""
        import csv
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Export Products to CSV",
            defaultextension=".csv",
            initialfile="inventory_products.csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            products = database.list_products()
            with open(path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["id", "name", "price", "cost_price", "stock", "min_stock"])
                for p in products:
                    writer.writerow([
                        p["id"], p["name"], p["price"],
                        p.get("cost_price", 0.0), p["stock"], p.get("min_stock", 5)
                    ])
            self.app.notify("Inventory exported to CSV successfully!")
        except Exception as exc:
            messagebox.showerror("Export Failed", str(exc))

    def _import_csv(self) -> None:
        """Import products from a CSV file (adds new or updates existing)."""
        import csv
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            parent=self,
            title="Select Products CSV File",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if not path:
            return
        imported_count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                if not reader.fieldnames or "name" not in [col.lower() for col in reader.fieldnames]:
                    messagebox.showerror(
                        "Invalid Format",
                        "CSV must contain at least a 'name' and 'price' column.\n"
                        "Columns supported: name, price, cost_price, stock, min_stock",
                    )
                    return
                for row in reader:
                    # Normalize keys
                    r = {k.strip().lower(): v.strip() for k, v in row.items() if k}
                    name = r.get("name")
                    if not name:
                        continue
                    price = float(r.get("price", "0.0") or 0.0)
                    cost = float(r.get("cost_price", r.get("cost", "0.0")) or 0.0)
                    stock = int(float(r.get("stock", "0") or 0))
                    database.add_product(name, price, stock, cost)
                    imported_count += 1

            self._refresh()
            self.app.refresh_low_stock_badge()
            self.app.notify(f"Imported {imported_count} products from CSV!", kind="success")
        except Exception as exc:
            messagebox.showerror("Import Error", f"Failed importing CSV:\n{exc}")

    def _generate_barcode_tag(self) -> None:
        """Generate and preview a printable shelf label with Code128 barcode and price."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Barcode Label", "Please select a product from the table first.")
            return

        values = self.tree.item(selection[0], "values")
        product_id = values[0]
        name = values[1]
        price = values[2]

        import barcode
        from barcode.writer import ImageWriter
        from io import BytesIO
        from PIL import Image, ImageTk

        try:
            # Generate Code128 barcode in memory
            code128 = barcode.get_barcode_class("code128")
            # Format product code as 8-digit numeric or alphanumeric string
            code_str = f"P{int(product_id):06d}"
            bc = code128(code_str, writer=ImageWriter())

            fp = BytesIO()
            bc.write(fp, options={"write_text": True, "font_size": 10, "text_distance": 4, "quiet_zone": 2})
            fp.seek(0)
            pil_img = Image.open(fp)
            pil_img = pil_img.resize((260, 100), Image.Resampling.LANCZOS)
        except Exception as exc:
            messagebox.showerror("Barcode Error", f"Could not generate barcode: {exc}")
            return

        # Pop up shelf label modal
        win = ctk.CTkToplevel(self)
        win.title("Shelf Price Tag & Barcode")
        win.geometry("380x360")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(win, text="🏷️ Product Shelf Tag", font=ctk.CTkFont(size=16, weight="bold")).pack(pady=(16, 4))

        # Tag card preview
        card = ctk.CTkFrame(win, corner_radius=12, fg_color="white", border_width=2, border_color="#cbd5e1")
        card.pack(fill="x", padx=30, pady=12)

        ctk.CTkLabel(card, text=self.app.settings.store_name.upper(), font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack(pady=(10, 2))
        ctk.CTkLabel(card, text=name, font=ctk.CTkFont(size=14, weight="bold"), text_color="#0f172a").pack(padx=10)
        ctk.CTkLabel(card, text=f"PRICE: {price}", font=ctk.CTkFont(size=18, weight="bold"), text_color="#10b981").pack(pady=(4, 6))

        tk_img = ImageTk.PhotoImage(pil_img)
        lbl = ctk.CTkLabel(card, image=tk_img, text="")
        lbl.image = tk_img  # retain reference
        lbl.pack(pady=(0, 10))

        def save_label():
            from tkinter import filedialog
            path = filedialog.asksaveasfilename(
                parent=win,
                title="Save Price Tag Image",
                defaultextension=".png",
                initialfile=f"tag_{code_str}.png",
                filetypes=[("PNG Image", "*.png"), ("All files", "*.*")],
            )
            if path:
                # Save full resolution label card
                lbl_full = Image.new("RGB", (340, 240), "white")
                from PIL import ImageDraw, ImageFont
                draw = ImageDraw.Draw(lbl_full)
                draw.text((20, 15), self.app.settings.store_name.upper(), fill="#64748b")
                draw.text((20, 35), name[:28], fill="black")
                draw.text((20, 65), f"PRICE: {price}", fill="#10b981")
                lbl_full.paste(pil_img, (40, 110))
                lbl_full.save(path)
                self.app.notify("Label tag saved successfully!")
                win.destroy()

        btn_row = ctk.CTkFrame(win, fg_color="transparent")
        btn_row.pack(pady=(4, 12))

        ctk.CTkButton(btn_row, text="💾 Save PNG Tag", width=120, height=32, corner_radius=8, command=save_label).pack(side="left", padx=6)
        ctk.CTkButton(btn_row, text="Close", width=90, height=32, corner_radius=8, fg_color="#64748b", hover_color="#475569", command=win.destroy).pack(side="left", padx=6)
