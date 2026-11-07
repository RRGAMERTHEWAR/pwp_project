"""Receipt Presentation View.

Renders the formatted receipt text for a completed transaction:
- Shows store header, customer details, line items, tax, discounts, and totals.
- Action buttons: 'Save Bill to DB', 'Print Receipt' (OS printer integration),
  and 'Export to PDF'.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import TYPE_CHECKING

import customtkinter as ctk

from core.calculations import Bill, format_receipt
from core.pdfexport import export_receipt_pdf
from db import database

if TYPE_CHECKING:  # pragma: no cover
    from ui.app import BillingApp


class ReceiptView(ctk.CTkFrame):
    """Read-only display of a generated bill with Save / Print / PDF actions."""

    def __init__(self, master: ctk.CTkFrame, app: "BillingApp", bill: Bill) -> None:
        super().__init__(master, corner_radius=0)
        self.app = app
        self.bill = bill
        self._build()
        self._render()

    def _build(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 0))
        ctk.CTkLabel(
            header, text="Bill Receipt", font=ctk.CTkFont(size=18, weight="bold")
        ).pack(side="left")
        ctk.CTkButton(
            header, text="◀ Back", width=90, command=self.app.show_billing
        ).pack(side="right")

        text_frame = ctk.CTkFrame(self, corner_radius=10)
        text_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=10)
        text_frame.grid_columnconfigure(0, weight=1)
        text_frame.grid_rowconfigure(0, weight=1)

        self.text = tk.Text(
            text_frame, wrap="none", font=("Consolas", 10), padx=10, pady=10,
            bg="#1a1a1a" if ctk.get_appearance_mode() == "Dark" else "#ffffff",
            fg="#f0f0f0" if ctk.get_appearance_mode() == "Dark" else "#111111",
            relief="flat", borderwidth=0, highlightthickness=0,
        )
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=yscroll.set)
        self.text.grid(row=0, column=0, sticky="nsew", padx=(8, 0), pady=8)
        yscroll.grid(row=0, column=1, sticky="ns", padx=(0, 8), pady=8)
        self.text.configure(state="disabled")

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 14))

        ctk.CTkButton(
            actions,
            text="📱 Payment QR",
            width=105,
            height=34,
            corner_radius=8,
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            command=self._show_payment_qr,
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="📲 Soft Copy QR",
            width=115,
            height=34,
            corner_radius=8,
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._show_soft_copy_qr,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions,
            text="💬 WhatsApp",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="#16a34a",
            hover_color="#15803d",
            command=self._send_whatsapp,
        ).pack(side="left")

        ctk.CTkButton(
            actions,
            text="📧 Email",
            width=85,
            height=34,
            corner_radius=8,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=self._send_email,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            actions,
            text="Print Slip",
            width=90,
            height=34,
            corner_radius=8,
            command=self._print,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="🧾 80mm Slip",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="#0891b2",
            hover_color="#0e7490",
            command=lambda: self._export_pdf(mode="80mm"),
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="📄 A4 Invoice",
            width=110,
            height=34,
            corner_radius=8,
            fg_color="#0284c7",
            hover_color="#0369a1",
            command=lambda: self._export_pdf(mode="A4"),
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            actions,
            text="Save to database",
            width=140,
            height=34,
            corner_radius=8,
            fg_color=("#10b981", "#059669"),
            hover_color=("#059669", "#047857"),
            font=ctk.CTkFont(weight="bold"),
            command=self._save,
        ).pack(side="right")

    def _show_payment_qr(self) -> None:
        """Generate and display dynamic UPI Payment QR code."""
        import qrcode
        from PIL import ImageTk

        upi_id = getattr(self.app.settings, "upi_id", "store@upi") or "store@upi"
        store_name = self.app.settings.store_name.replace(" ", "%20")
        amount = f"{self.bill.total:.2f}"

        # Standard UPI intent URL
        upi_url = f"upi://pay?pa={upi_id}&pn={store_name}&am={amount}&cu=INR"

        qr = qrcode.QRCode(box_size=6, border=2)
        qr.add_data(upi_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Display in modern CTk dialog
        win = ctk.CTkToplevel(self)
        win.title("Payment QR Code")
        win.geometry("340x440")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(
            win,
            text=f"Scan to Pay: {self.app.settings.currency}{self.bill.total:,.2f}",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(20, 6))

        ctk.CTkLabel(
            win,
            text=f"UPI ID: {upi_id}",
            text_color="gray",
            font=ctk.CTkFont(size=12),
        ).pack(pady=(0, 14))

        tk_img = ImageTk.PhotoImage(img)
        lbl = tk.Label(win, image=tk_img, bg="white")
        lbl.image = tk_img  # prevent garbage collection
        lbl.pack(pady=6)

        ctk.CTkButton(
            win,
            text="Done / Close",
            width=140,
            height=32,
            corner_radius=8,
            command=win.destroy,
        ).pack(pady=(16, 12))

    def _show_soft_copy_qr(self) -> None:
        """Generate and display QR code encoding the complete itemized soft copy of the bill."""
        import qrcode
        from PIL import ImageTk

        summary = self.bill.digital_summary(
            store_name=self.app.settings.store_name,
            currency=self.app.settings.currency,
        )

        qr = qrcode.QRCode(box_size=5, border=2)
        qr.add_data(summary)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        win = ctk.CTkToplevel(self)
        win.title("Bill Soft-Copy QR")
        win.geometry("380x500")
        win.resizable(False, False)
        win.grab_set()

        ctk.CTkLabel(
            win,
            text="📲 Scan for Digital Bill",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(pady=(18, 4))

        ctk.CTkLabel(
            win,
            text="Customers can scan this with any phone camera to get the full receipt",
            text_color="gray",
            font=ctk.CTkFont(size=11),
            wraplength=340,
        ).pack(pady=(0, 10))

        tk_img = ImageTk.PhotoImage(img)
        lbl = tk.Label(win, image=tk_img, bg="white")
        lbl.image = tk_img  # prevent garbage collection
        lbl.pack(pady=4)

        ctk.CTkButton(
            win,
            text="Close",
            width=120,
            height=32,
            corner_radius=8,
            command=win.destroy,
        ).pack(pady=(14, 10))

    def _show_qr(self) -> None:
        """Backwards compatibility alias for _show_payment_qr."""
        self._show_payment_qr()

    def _send_whatsapp(self) -> None:
        """Open WhatsApp chat with an itemized receipt message for the customer."""
        import urllib.parse
        import webbrowser

        phone = "".join(c for c in (self.bill.customer_phone or "") if c.isdigit())
        if not phone:
            phone = ""

        # Compose WhatsApp receipt text
        items_summary = "\n".join(
            f"• {it.description} x {it.qty} = {self.app.settings.currency}{it.line_total:.2f}"
            for it in self.bill.items
        )
        msg = (
            f"*🧾 {self.app.settings.store_name} — E-Receipt*\n"
            f"Date: {self.bill.created_at:%Y-%m-%d %H:%M}\n"
            f"Customer: {self.bill.customer_name or 'Valued Customer'}\n"
            f"---------------------------\n"
            f"{items_summary}\n"
            f"---------------------------\n"
            f"*Grand Total: {self.app.settings.currency}{self.bill.total:.2f}*\n"
            f"Payment Method: {self.bill.payment_method}\n\n"
            f"Thank you for shopping with us! 🙏"
        )
        encoded_msg = urllib.parse.quote(msg)
        wa_url = f"https://wa.me/{phone}?text={encoded_msg}" if phone else f"https://wa.me/?text={encoded_msg}"
        webbrowser.open(wa_url)
        self.app.notify("Opening WhatsApp with digital receipt...", kind="info")

    def _send_email(self) -> None:
        """Send the receipt PDF to customer's email via configured SMTP server."""
        import smtplib
        import tempfile
        from email.message import EmailMessage

        settings = self.app.settings
        recipient = (self.bill.customer_email or "").strip()
        if not recipient:
            messagebox.showwarning("Email Receipt", "No customer email address on this invoice.")
            return

        if not settings.smtp_server or not settings.smtp_user:
            messagebox.showwarning(
                "SMTP Not Configured",
                "Please configure your SMTP Server & Credentials in Settings → System & Security first.",
            )
            return

        try:
            # Generate temporary receipt PDF
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                temp_pdf_path = tmp.name
            export_receipt_pdf(self.bill, temp_pdf_path, settings, format_mode="A4")

            # Build email message
            msg = EmailMessage()
            msg["Subject"] = f"Invoice from {settings.store_name} (#{self.bill.created_at:%y%m%d%H%M})"
            msg["From"] = settings.smtp_user
            msg["To"] = recipient
            msg.set_content(
                f"Dear {self.bill.customer_name or 'Customer'},\n\n"
                f"Thank you for your purchase at {settings.store_name}.\n"
                f"Please find your invoice attached.\n\n"
                f"Total Paid: {settings.currency}{self.bill.total:.2f}\n"
                f"Date: {self.bill.created_at:%Y-%m-%d %H:%M}\n\n"
                f"Warm regards,\n{settings.store_name}"
            )

            with open(temp_pdf_path, "rb") as f:
                pdf_data = f.read()
            msg.add_attachment(pdf_data, maintype="application", subtype="pdf", filename=f"invoice_{self.bill.created_at:%Y%m%d}.pdf")

            # Dispatch via SMTP
            with smtplib.SMTP(settings.smtp_server, settings.smtp_port, timeout=10) as server:
                server.starttls()
                if settings.smtp_pass:
                    server.login(settings.smtp_user, settings.smtp_pass)
                server.send_message(msg)

            self.app.notify(f"Invoice emailed to {recipient}!", kind="success")
        except Exception as exc:
            messagebox.showerror("Email Failed", f"Could not send email: {exc}")

    def _render(self) -> None:
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.insert("1.0", format_receipt(self.bill, settings=self.app.settings))
        self.text.configure(state="disabled")

    # -- actions -------------------------------------------------------------

    def _save(self) -> None:
        try:
            bill_id = database.save_bill(self.bill, user_id=self.app.user["id"])
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror("Save failed", str(exc))
            return
        messagebox.showinfo("Saved", f"Bill #{bill_id} saved.\nInventory and loyalty updated.")
        self.app.show_billing()

    def _export_pdf(self, mode: str = "A4") -> None:
        prefix = "slip_80mm" if mode == "80mm" else "invoice_a4"
        default_name = f"{prefix}_{self.bill.created_at:%Y%m%d_%H%M%S}.pdf"
        path = filedialog.asksaveasfilename(
            parent=self, title=f"Export receipt as ({mode}) PDF", defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            export_receipt_pdf(self.bill, path, self.app.settings, format_mode=mode)
        except Exception as exc:  # pragma: no cover - defensive
            messagebox.showerror("Export failed", str(exc))
            return
        self.app.notify(f"Exported {mode} receipt successfully!")

    def _print(self) -> None:
        """Best-effort print: write a temp file and let the OS handle it."""
        text = format_receipt(self.bill, settings=self.app.settings)
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".txt", delete=False, encoding="utf-8"
            )
            tmp.write(text)
            tmp.close()
            if sys.platform.startswith("win"):
                os.startfile(tmp.name, "print")  # type: ignore[attr-defined]
            else:
                subprocess.run(["lpr", tmp.name], check=False)
        except Exception as exc:
            messagebox.showerror(
                "Print failed",
                f"Couldn't print automatically ({exc}).\nThe receipt is on screen — "
                "copy/paste into any text editor to print.",
            )
