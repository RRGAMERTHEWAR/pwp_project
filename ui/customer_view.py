"""Customer Relationship Management (CRM) View.

Displays customer profiles, phone numbers, emails, and their loyalty points balances.
Allows searching existing customers and updating contact information or point balances.
"""

from __future__ import annotations

from tkinter import messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk

from db import database

if TYPE_CHECKING:  # pragma: no cover
    from ui.app import BillingApp


class CustomerView(ctk.CTkFrame):
    """View, search, and edit customer details and loyalty balances."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp") -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self._build()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 6))
        header.grid_columnconfigure(3, weight=1)
        
        ctk.CTkLabel(header, text="Customers (CRM)", font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w", padx=(0, 20))

        self.search_var = ctk.StringVar()
        search_entry = ctk.CTkEntry(header, textvariable=self.search_var, placeholder_text="Search Name or Phone", width=200)
        search_entry.grid(row=0, column=1, padx=6)
        search_entry.bind("<KeyRelease>", lambda _e: self._refresh_customers())

        ctk.CTkButton(header, text="Search", width=80, command=self._refresh_customers).grid(row=0, column=2, padx=6)

        # Edit Form
        form = ctk.CTkFrame(self, corner_radius=10)
        form.grid(row=1, column=0, sticky="ew", padx=14, pady=8)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)
        form.grid_columnconfigure(5, weight=2)
        
        self.c_id = ctk.StringVar()
        self.c_name = ctk.StringVar()
        self.c_phone = ctk.StringVar()
        self.c_email = ctk.StringVar()
        
        ctk.CTkLabel(form, text="Name:").grid(row=0, column=0, padx=(14, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.c_name, placeholder_text="Customer Name").grid(row=0, column=1, sticky="ew", padx=4, pady=12)
        
        ctk.CTkLabel(form, text="Phone:").grid(row=0, column=2, padx=(12, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.c_phone, placeholder_text="Phone Number").grid(row=0, column=3, sticky="ew", padx=4, pady=12)
        
        ctk.CTkLabel(form, text="Email:").grid(row=0, column=4, padx=(12, 4), pady=12)
        ctk.CTkEntry(form, textvariable=self.c_email, placeholder_text="Email Address").grid(row=0, column=5, sticky="ew", padx=4, pady=12)
        
        ctk.CTkButton(
            form,
            text="Save Changes",
            width=120,
            height=34,
            corner_radius=8,
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            font=ctk.CTkFont(weight="bold"),
            command=self._save_customer,
        ).grid(row=0, column=6, padx=(12, 14), pady=12)

        # Table
        table_frame = ctk.CTkFrame(self, corner_radius=10)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=14, pady=(8, 14))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            table_frame, columns=("id", "name", "phone", "email", "loyalty", "joined"),
            show="headings", selectmode="browse",
        )
        for col, text in [("id", "ID"), ("name", "Name"), ("phone", "Phone"), ("email", "Email"), ("loyalty", "Loyalty Balance"), ("joined", "Joined")]:
            self.tree.heading(col, text=text)
        self.tree.column("id", width=50, stretch=False)
        self.tree.column("name", width=150)
        self.tree.column("phone", width=120)
        self.tree.column("email", width=180)
        self.tree.column("loyalty", width=120)
        self.tree.column("joined", width=140)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        
        yscroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        yscroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)

        self._refresh_customers()

    def _refresh_customers(self) -> None:
        self.tree.delete(*self.tree.get_children())
        search = self.search_var.get().strip()
        
        for c in database.list_customers(name=search, phone=search):
            self.tree.insert("", "end", values=(
                c["id"], c["name"], c.get("phone", ""), c.get("email", ""), 
                c["loyalty_balance"], c["created_at"][:10]
            ))

    def _on_select(self, event: object) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        item = self.tree.item(selection[0], "values")
        self.c_id.set(item[0])
        self.c_name.set(item[1])
        self.c_phone.set(item[2])
        self.c_email.set(item[3])

    def _save_customer(self) -> None:
        c_id = self.c_id.get()
        if not c_id:
            messagebox.showwarning("Customer", "Select a customer to edit.")
            return
        
        name = self.c_name.get().strip()
        if not name:
            messagebox.showerror("Error", "Name cannot be empty.")
            return
            
        with database.connect() as conn:
            conn.execute(
                "UPDATE customers SET name = ?, phone = ?, email = ? WHERE id = ?",
                (name, self.c_phone.get().strip(), self.c_email.get().strip(), c_id)
            )
        self.app.notify("Customer profile updated successfully!")
        self._refresh_customers()
