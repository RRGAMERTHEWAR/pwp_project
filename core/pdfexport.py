"""PDF Export helper for Receipts and History Reports.

Uses `fpdf2` to produce printable PDF receipts and bill history documents.
Automatically discovers and embeds Unicode fonts (such as DejaVu Sans or Arial)
to render currency signs like ₹ or € properly.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime

import matplotlib
import qrcode
from fpdf import FPDF

from core.calculations import Bill
from core.settings import Settings


def _unicode_font_path() -> str | None:
    """Find a TrueType font on the local system that supports Unicode symbols."""
    candidates = [
        os.path.join(
            os.path.dirname(matplotlib.__file__), "mpl-data", "fonts", "ttf",
            "DejaVuSans.ttf",
        ),
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\segoeui.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


_FONT_PATH = _unicode_font_path()
_UNICODE_FAMILY = "Uni"  # family name registered from the TTF above


class _Pdf(FPDF):
    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title
        if _FONT_PATH is not None:
            try:
                self.add_font(_UNICODE_FAMILY, "", _FONT_PATH)
                self.add_font(_UNICODE_FAMILY, "B", _FONT_PATH)
            except Exception:
                pass
        self.add_page()

    def header(self) -> None:
        self._body_font(14, bold=True)
        self.cell(0, 8, self._title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self) -> None:
        self.set_y(-15)
        self._body_font(8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def _body_font(self, size: int, *, bold: bool = False) -> None:
        if _FONT_PATH is not None:
            self.set_font(_UNICODE_FAMILY, "B" if bold else "", size)
        else:
            self.set_font("helvetica", "B" if bold else "", size)

    def _text(self, value: object) -> str:
        text = str(value)
        if _FONT_PATH is None:
            text = text.replace("\u20b9", "Rs.")
        return text


def _sanitize_rows(rows: list[tuple[str, object]]) -> list[tuple[str, str]]:
    """Convert values to safe strings (fallback replaces ₹)."""
    out: list[tuple[str, str]] = []
    for label, value in rows:
        text = str(value)
        if _FONT_PATH is None:
            text = text.replace("\u20b9", "Rs.")
        out.append((str(label), text))
    return out


def export_receipt_pdf(bill: Bill, path: str, settings: Settings, format_mode: str = "A4") -> None:
    """Write *bill* to a receipt PDF at *path* in either 'A4' or '80mm' thermal slip format."""
    currency = settings.currency

    if format_mode == "80mm":
        # 80mm roll width is approx 80mm x 200mm (or dynamic length)
        # Calculate dynamic page height based on number of items
        item_count = len(bill.items)
        calc_height = max(140.0, 90.0 + (item_count * 9.0))
        pdf = FPDF(unit="mm", format=(80.0, calc_height))
        if _FONT_PATH is not None:
            try:
                pdf.add_font(_UNICODE_FAMILY, "", _FONT_PATH)
                pdf.add_font(_UNICODE_FAMILY, "B", _FONT_PATH)
            except Exception:
                pass
        pdf.set_margins(4, 4, 4)
        pdf.set_auto_page_break(False)
        pdf.add_page()

        # Helper font setting
        def use_font(size: int = 8, bold: bool = False):
            family = _UNICODE_FAMILY if _FONT_PATH else "Helvetica"
            pdf.set_font(family, "B" if bold else "", size)

        use_font(11, bold=True)
        pdf.cell(72, 6, settings.store_name, align="C", new_x="LMARGIN", new_y="NEXT")
        use_font(8)
        pdf.cell(72, 4, f"Receipt #{bill.created_at:%y%m%d%H%M%S}", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(72, 4, f"Date: {bill.created_at:%Y-%m-%d %H:%M}", align="C", new_x="LMARGIN", new_y="NEXT")
        if bill.customer_name:
            pdf.cell(72, 4, f"Cust: {bill.customer_name} ({bill.customer_phone or ''})", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.line(4, pdf.get_y() + 1, 76, pdf.get_y() + 1)
        pdf.ln(3)

        # Thermal items table (width total = 72mm)
        use_font(8, bold=True)
        pdf.cell(34, 5, "Item", border=0)
        pdf.cell(10, 5, "Qty", align="C", border=0)
        pdf.cell(14, 5, "Price", align="R", border=0)
        pdf.cell(14, 5, "Total", align="R", new_x="LMARGIN", new_y="NEXT", border=0)
        use_font(8)
        for it in bill.items:
            desc = (it.description or "")[:18]
            pdf.cell(34, 4, desc, border=0)
            pdf.cell(10, 4, str(it.qty), align="C", border=0)
            pdf.cell(14, 4, f"{it.unit_price:.1f}", align="R", border=0)
            pdf.cell(14, 4, f"{it.line_total:.1f}", align="R", new_x="LMARGIN", new_y="NEXT", border=0)

        pdf.line(4, pdf.get_y() + 1, 76, pdf.get_y() + 1)
        pdf.ln(3)

        # Totals
        pdf.cell(44, 4, "Subtotal:")
        pdf.cell(28, 4, f"{currency}{bill.subtotal:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
        if bill.discount > 0:
            pdf.cell(44, 4, "Discount:")
            pdf.cell(28, 4, f"-{currency}{bill.discount:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
        if bill.points_redeemed > 0:
            pdf.cell(44, 4, "Loyalty Redeemed:")
            pdf.cell(28, 4, f"-{currency}{bill.points_redeemed:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
        pdf.cell(44, 4, f"Tax ({settings.tax_rate:.0f}%):")
        pdf.cell(28, 4, f"{currency}{bill.tax:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

        use_font(10, bold=True)
        pdf.cell(44, 6, "GRAND TOTAL:")
        pdf.cell(28, 6, f"{currency}{bill.total:.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

        # Dynamic QR code embedding (Payment & Digital Soft Copy)
        try:
            upi_id = getattr(settings, "upi_id", "") or "store@upi"
            st_name = settings.store_name.replace(" ", "%20")
            amt = f"{bill.total:.2f}"
            upi_payload = f"upi://pay?pa={upi_id}&pn={st_name}&am={amt}&cu=INR"

            qr = qrcode.QRCode(box_size=4, border=1)
            qr.add_data(upi_payload)
            qr.make(fit=True)
            qr_img = qr.make_image(fill_color="black", back_color="white")

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                qr_tmp_path = tf.name
                qr_img.save(qr_tmp_path)

            pdf.ln(2)
            # Center a 26mm x 26mm QR code on the 80mm slip
            qr_x = (80.0 - 26.0) / 2
            pdf.image(qr_tmp_path, x=qr_x, y=pdf.get_y(), w=26, h=26)
            pdf.set_y(pdf.get_y() + 27)
            try:
                os.remove(qr_tmp_path)
            except OSError:
                pass
            use_font(7, bold=True)
            pdf.cell(72, 3, "Scan to Pay / Verify Bill", align="C", new_x="LMARGIN", new_y="NEXT")
        except Exception:
            pass

        use_font(7)
        pdf.ln(2)
        pdf.cell(72, 4, "Thank you for shopping with us!", align="C", new_x="LMARGIN", new_y="NEXT")
        pdf.output(path)
        return

    # Standard A4 PDF export
    pdf = _Pdf(f"{settings.store_name} — Receipt #{bill.created_at:%Y%m%d-%H%M%S}")

    pdf._body_font(10)
    for label, value in [
        ("Date", f"{bill.created_at:%Y-%m-%d %H:%M:%S}"),
        ("Customer", bill.customer_name or "-"),
        ("Phone", bill.customer_phone),
        ("Email", bill.customer_email),
    ]:
        if value:
            pdf.cell(0, 6, f"{label}: {value}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Items table
    col_widths = (18, 62, 18, 26, 26)
    headers = ("#", "Item", "Qty", "Price", "Total")
    pdf._body_font(9, bold=True)
    pdf.set_fill_color(235, 235, 235)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, pdf._text(h), border=1, fill=True)
    pdf.ln()

    pdf._body_font(9)
    for idx, item in enumerate(bill.items, start=1):
        desc = (item.description or "")[:30]
        pdf.cell(col_widths[0], 6, pdf._text(idx), border=1)
        pdf.cell(col_widths[1], 6, pdf._text(desc), border=1)
        pdf.cell(col_widths[2], 6, pdf._text(item.qty), border=1)
        pdf.cell(col_widths[3], 6, pdf._text(f"{currency}{item.unit_price:.2f}"), border=1)
        pdf.cell(col_widths[4], 6, pdf._text(f"{currency}{item.line_total:.2f}"), border=1)
        pdf.ln()

    pdf.ln(4)
    rows: list[tuple[str, object]] = [("Subtotal", f"{currency}{bill.subtotal:.2f}")]
    if bill.discount:
        rows.append(("Discount", f"-{currency}{bill.discount:.2f}"))
    if bill.points_redeemed:
        rows.append(("Loyalty redeemed", f"-{currency}{bill.points_redeemed:.2f}"))
    rows.append((f"Tax ({settings.tax_rate:.0f}%)", f"{currency}{bill.tax:.2f}"))
    rows.append(("Loyalty points earned", str(bill.loyalty_points)))
    if bill.points_used:
        rows.append(("Points redeemed", str(bill.points_used)))

    pdf._body_font(10)
    for label, value in _sanitize_rows(rows):
        pdf.cell(80, 7, pdf._text(label))
        pdf.cell(0, 7, pdf._text(value), align="R", new_x="LMARGIN", new_y="NEXT")

    pdf._body_font(12, bold=True)
    pdf.cell(80, 9, pdf._text("TOTAL PAYABLE"))
    pdf.cell(0, 9, pdf._text(f"{currency}{bill.total:.2f}"), align="R",
             new_x="LMARGIN", new_y="NEXT")

    # Dual QR Codes on A4 invoice:
    # 1. Payment QR (UPI / Bank transfer)
    # 2. Digital Soft-Copy QR (scan with phone camera to view full itemized bill text)
    try:
        upi_id = getattr(settings, "upi_id", "") or "store@upi"
        st_name = settings.store_name.replace(" ", "%20")
        amt = f"{bill.total:.2f}"
        upi_payload = f"upi://pay?pa={upi_id}&pn={st_name}&am={amt}&cu=INR"
        soft_copy_payload = bill.digital_summary(store_name=settings.store_name, currency=currency)

        # Generate Payment QR
        qr_pay = qrcode.QRCode(box_size=4, border=1)
        qr_pay.add_data(upi_payload)
        qr_pay.make(fit=True)
        img_pay = qr_pay.make_image(fill_color="black", back_color="white")

        # Generate Soft Copy QR
        qr_copy = qrcode.QRCode(box_size=4, border=1)
        qr_copy.add_data(soft_copy_payload)
        qr_copy.make(fit=True)
        img_copy = qr_copy.make_image(fill_color="black", back_color="white")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf1:
            p1 = tf1.name
            img_pay.save(p1)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf2:
            p2 = tf2.name
            img_copy.save(p2)

        pdf.ln(6)
        curr_y = pdf.get_y()
        if curr_y > 230:
            pdf.add_page()
            curr_y = pdf.get_y()

        # Render side-by-side QR codes
        qr_size = 32
        pdf.image(p1, x=25, y=curr_y, w=qr_size, h=qr_size)
        pdf.image(p2, x=140, y=curr_y, w=qr_size, h=qr_size)

        pdf.set_y(curr_y + qr_size + 2)
        pdf._body_font(8, bold=True)
        pdf.set_x(15)
        pdf.cell(52, 4, pdf._text("Scan to Pay (UPI)"), align="C")
        pdf.set_x(130)
        pdf.cell(52, 4, pdf._text("Scan for Digital Soft Copy"), align="C", new_x="LMARGIN", new_y="NEXT")

        try:
            os.remove(p1)
            os.remove(p2)
        except OSError:
            pass
    except Exception:
        pass

    pdf.output(path)


def export_history_pdf(
    rows: list[dict], path: str, settings: Settings, title: str = "Bill History"
) -> None:
    """Write bill-history *rows* (as returned by database.search_bills) to PDF."""
    pdf = _Pdf(f"{settings.store_name} — {title}")
    currency = settings.currency
    pdf._body_font(9)
    pdf.cell(0, 6, pdf._text(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}"),
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    col_widths = (14, 30, 52, 30, 22, 34)
    headers = ("ID", "Date", "Customer", "Phone", "Pts", "Total")
    pdf._body_font(9, bold=True)
    pdf.set_fill_color(235, 235, 235)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 7, pdf._text(h), border=1, fill=True)
    pdf.ln()

    pdf._body_font(9)
    for r in rows:
        created = str(r.get("created_at", ""))[:10]
        pdf.cell(col_widths[0], 6, pdf._text(r.get("id", "")), border=1)
        pdf.cell(col_widths[1], 6, pdf._text(created), border=1)
        pdf.cell(col_widths[2], 6, pdf._text(str(r.get("customer_name", ""))[:24]), border=1)
        pdf.cell(col_widths[3], 6, pdf._text(r.get("phone", "")), border=1)
        pdf.cell(col_widths[4], 6, pdf._text(r.get("loyalty_points", 0)), border=1)
        pdf.cell(col_widths[5], 6, pdf._text(f"{currency}{r.get('total', 0.0):.2f}"), border=1)
        pdf.ln()

    pdf.ln(3)
    total = sum(r.get("total", 0.0) for r in rows)
    pdf._body_font(10, bold=True)
    pdf.cell(80, 8, pdf._text(f"Total bills: {len(rows)}"))
    pdf.cell(0, 8, pdf._text(f"Grand total: {currency}{total:.2f}"),
             align="R", new_x="LMARGIN", new_y="NEXT")
    pdf.output(path)
