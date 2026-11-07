"""Pure calculation helpers for the billing system.

This module contains pure math and data structures for bills and items:
- Input validation (validating quantity and money amounts)
- Subtotal, tier discounts, coupon codes, tax, and loyalty points calculations
- LineItem and Bill dataclasses used throughout the UI and database layers
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence

from core.settings import Settings


# ---------------- Default Business Rules ----------------
# Used as fallbacks when a Settings instance isn't passed explicitly
TAX_RATE = 0.05                # 5% tax on the discounted subtotal
LOYALTY_POINTS_PER_100 = 1     # 1 point earned per 100 spent
DEFAULT_REDEMPTION_RATE = 1.0  # 1 loyalty point = 1.00 currency unit discount

# Discount tiers: (min_subtotal, rate) evaluated from highest to lowest threshold
DISCOUNT_TIERS: Sequence[tuple[float, float]] = (
    (5000.0, 0.10),  # 10% off for orders over 5000
    (2000.0, 0.05),  # 5% off for orders over 2000
)


# --- validation ---------------------------------------------------------------

class ValidationError(ValueError):
    """Raised when a user-entered value can't be used in calculations."""


def validate_amount(raw: object, *, field: str = "amount") -> float:
    """Coerce *raw* to a positive float. Raises ValidationError on bad input."""
    if raw is None or raw == "":
        raise ValidationError(f"{field} is required")
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number (got {raw!r})")
    if value < 0:
        raise ValidationError(f"{field} cannot be negative (got {value})")
    return value


def validate_int(raw: object, *, field: str = "quantity") -> int:
    """Like validate_amount but for integer quantities (accepts ``"3"`` and
    ``"3.0"`` but rejects ``"3.5"``)."""
    if raw is None or raw == "":
        raise ValidationError(f"{field} is required")
    try:
        as_float = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a whole number (got {raw!r})")
    if as_float != int(as_float):
        raise ValidationError(f"{field} must be a whole number (got {raw!r})")
    value = int(as_float)
    if value <= 0:
        raise ValidationError(f"{field} must be at least 1 (got {value})")
    return value


# --- core math ----------------------------------------------------------------

def calculate_discount(subtotal: float, *, settings: Settings | None = None) -> float:
    """Return the tier discount amount for *subtotal*."""
    tiers = settings.tiers if settings is not None else DISCOUNT_TIERS
    for threshold, rate in tiers:
        if subtotal >= threshold:
            return round(subtotal * rate, 2)
    return 0.0


def calculate_tax(
    taxable_amount: float, *, settings: Settings | None = None
) -> float:
    """Apply the configured tax rate to *taxable_amount*."""
    rate = settings.tax_rate_fraction if settings is not None else TAX_RATE
    return round(taxable_amount * rate, 2)


def calculate_loyalty_points(
    final_total: float, *, settings: Settings | None = None
) -> int:
    """Points earned for *final_total* (per full 100 currency units)."""
    per_100 = (
        settings.loyalty_points_per_100
        if settings is not None
        else LOYALTY_POINTS_PER_100
    )
    return int(final_total // 100) * per_100


def redemption_value(points_used: int, *, settings: Settings | None = None) -> float:
    """Currency value of *points_used* loyalty points."""
    rate = (
        settings.loyalty_redemption_rate
        if settings is not None
        else DEFAULT_REDEMPTION_RATE
    )
    return round(points_used * rate, 2)


def final_payable(subtotal: float, discount: float, tax: float) -> float:
    """subtotal - discount + tax, rounded to 2dp."""
    return round(subtotal - discount + tax, 2)


# --- bill + receipt -----------------------------------------------------------

@dataclass(frozen=True)
class LineItem:
    description: str
    qty: int
    unit_price: float
    product_id: int | None = None
    unit_cost: float = 0.0

    @property
    def line_total(self) -> float:
        return round(self.qty * self.unit_price, 2)


@dataclass
class Bill:
    customer_id: int | None
    customer_name: str
    customer_phone: str
    customer_email: str
    items: list[LineItem]
    subtotal: float
    discount: float          # tier discount only
    points_used: int         # loyalty points redeemed on this bill
    points_redeemed: float   # currency value of the redeemed points
    tax: float
    loyalty_points: int      # points earned on this bill
    total: float
    payment_method: str
    created_at: datetime

    @classmethod
    def from_items(
        cls,
        *,
        customer: dict,
        items: Iterable[LineItem],
        settings: Settings | None = None,
        points_used: int = 0,
        max_points: int | None = None,
        payment_method: str = "Cash",
        coupon_code: str = "",
    ) -> "Bill":
        items = list(items)
        if not items:
            raise ValidationError("At least one line item is required")

        subtotal = round(sum(it.line_total for it in items), 2)
        tier_discount = calculate_discount(subtotal, settings=settings)

        # Apply coupon code if valid
        coupon_discount = 0.0
        if coupon_code and settings and getattr(settings, "coupons", None):
            code_upper = coupon_code.strip().upper()
            if code_upper in settings.coupons:
                pct = float(settings.coupons[code_upper])
                coupon_discount = round(subtotal * (pct / 100.0), 2)

        total_discount = round(tier_discount + coupon_discount, 2)

        # Redemption is capped by what the customer actually owns and by the
        # bill size, so nobody can spend more than they have or get money back.
        points_used = max(int(points_used or 0), 0)
        if max_points is not None:
            points_used = min(points_used, max(max_points, 0))
        rate = (
            settings.loyalty_redemption_rate if settings is not None
            else DEFAULT_REDEMPTION_RATE
        )
        redeem_value = min(
            redemption_value(points_used, settings=settings),
            round(subtotal - total_discount, 2),
        )
        if rate > 0 and redeem_value > 0:
            points_used = int(redeem_value / rate)

        taxable = max(0.0, round(subtotal - total_discount - redeem_value, 2))
        tax = calculate_tax(taxable, settings=settings)
        total = round(taxable + tax, 2)
        points_earned = calculate_loyalty_points(total, settings=settings)

        return cls(
            customer_id=customer.get("id"),
            customer_name=customer.get("name", "").strip(),
            customer_phone=customer.get("phone", "").strip(),
            customer_email=customer.get("email", "").strip(),
            items=items,
            subtotal=subtotal,
            discount=total_discount,
            points_used=points_used,
            points_redeemed=redeem_value,
            tax=tax,
            loyalty_points=points_earned,
            total=total,
            payment_method=payment_method,
            created_at=datetime.now(),
        )


def format_receipt(
    bill: Bill, *, settings: Settings | None = None, width: int = 48
) -> str:
    """Return a printable plain-text receipt."""
    store = settings.store_name if settings is not None else "My Store"
    currency = settings.currency if settings is not None else "\u20b9"
    tax_pct = (
        settings.tax_rate if settings is not None else TAX_RATE * 100
    )
    rule = "=" * width
    lines: list[str] = []
    lines.append(rule)
    lines.append(store.center(width))
    lines.append("CUSTOMER BILLING RECEIPT".center(width))
    lines.append(rule)
    lines.append(f"Date : {bill.created_at:%Y-%m-%d %H:%M:%S}")
    lines.append(f"Name : {bill.customer_name or '-'}")
    if bill.customer_phone:
        lines.append(f"Phone: {bill.customer_phone}")
    if bill.customer_email:
        lines.append(f"Email: {bill.customer_email}")
    lines.append("-" * width)
    lines.append(f"{'Item':<22}{'Qty':>5}{'Price':>9}{'Total':>10}")
    lines.append("-" * width)
    for it in bill.items:
        desc = (it.description or "")[:22]
        lines.append(f"{desc:<22}{it.qty:>5}{it.unit_price:>9.2f}{it.line_total:>10.2f}")
    lines.append("-" * width)
    lines.append(f"{'Subtotal':<38}{bill.subtotal:>10.2f}")
    if bill.discount:
        lines.append(f"{'Discount':<38}{bill.discount:>10.2f}")
    if bill.points_redeemed:
        lines.append(f"{'Loyalty redeemed':<38}{bill.points_redeemed:>10.2f}")
    lines.append(f"{'Tax (' + f'{tax_pct:.0f}%' + ')':<38}{bill.tax:>10.2f}")
    lines.append(f"{'Loyalty Points Earned':<38}{bill.loyalty_points:>10d}")
    if bill.points_used:
        lines.append(f"{'Points Redeemed':<38}{bill.points_used:>10d}")
    lines.append(rule)
    lines.append(f"{'TOTAL PAYABLE':<38}{currency}{bill.total:>9.2f}")
    lines.append(f"{'Payment Method':<38}{bill.payment_method:>9}")
    lines.append(rule)
    
    if settings is not None:
        if settings.bank_details:
            lines.append("Bank Transfer:")
            lines.append(settings.bank_details.center(width))
        if settings.crypto_wallet:
            lines.append("Crypto Wallet:")
            lines.append(settings.crypto_wallet.center(width))
        if settings.bank_details or settings.crypto_wallet:
            lines.append(rule)
            
    lines.append("Thank you for your business!".center(width))
    return "\n".join(lines)
