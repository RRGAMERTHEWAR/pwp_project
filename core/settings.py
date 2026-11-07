"""Store configuration and persistent settings manager.

Loads, validates, and saves business settings from/to `config.json` next to `main.py`.
Allows changing store parameters (name, currency, taxes, discounts, loyalty rules)
without modifying any code.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field


# Discount tier format: [min_subtotal_amount, discount_percentage]
# Example: [2000.0, 5.0] means 5% discount on bills >= 2000
@dataclass
class Settings:
    """Store profile, tax parameters, and payment configurations."""
    store_name: str = "My Store"
    currency: str = "\u20b9"  # Default: ₹ (Rupee), can be changed to $, €, etc.
    tax_rate: float = 5.0     # Percentage (5.0 = 5% tax applied after discount)
    appearance_mode: str = "System"  # "System", "Dark", or "Light"
    discount_tiers: list = field(
        default_factory=lambda: [[2000.0, 5.0], [5000.0, 10.0]]
    )
    payment_methods: list = field(
        default_factory=lambda: ["Cash", "Card", "UPI", "Crypto"]
    )
    coupons: dict = field(
        default_factory=lambda: {"WELCOME10": 10.0, "SAVE5": 5.0, "FESTIVE20": 20.0}
    )
    upi_id: str = "store@upi"
    bank_details: str = ""
    crypto_wallet: str = ""
    loyalty_points_per_100: int = 1       # Points rewarded per 100 spent
    loyalty_redemption_rate: float = 1.0  # Discount value of each point redeemed
    backup_dir: str = ""
    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""

    @property
    def tax_rate_fraction(self) -> float:
        """Tax rate converted to a decimal (e.g. 5.0% -> 0.05)."""
        return self.tax_rate / 100.0

    @property
    def tiers(self) -> list[tuple[float, float]]:
        """Discount tiers sorted from highest minimum amount to lowest."""
        return sorted(
            ((float(t[0]), float(t[1]) / 100.0) for t in self.discount_tiers),
            reverse=True,
        )

    def validate(self) -> None:
        """Sanity check settings values before saving to config.json."""
        if self.store_name.strip() == "":
            raise ValueError("Store name cannot be empty")
        if self.tax_rate < 0 or self.tax_rate > 100:
            raise ValueError("Tax rate must be between 0 and 100")
        if self.loyalty_points_per_100 < 0:
            raise ValueError("Loyalty points per 100 must be >= 0")
        if self.loyalty_redemption_rate < 0:
            raise ValueError("Loyalty redemption rate must be >= 0")
        if self.smtp_port < 1 or self.smtp_port > 65535:
            raise ValueError("SMTP port must be between 1 and 65535")
        for tier in self.discount_tiers:
            if len(tier) != 2:
                raise ValueError("Each discount tier needs [min amount, percent]")
            if tier[1] < 0 or tier[1] > 100:
                raise ValueError("Discount percent must be between 0 and 100")


def _config_path() -> str:
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(here, "config.json")


def load() -> Settings:
    """Load settings from config.json, falling back to defaults."""
    settings = Settings()
    path = _config_path()
    if not os.path.exists(path):
        return settings
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            return settings
        for key, value in data.items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    except (OSError, ValueError, TypeError):
        return settings
    return settings


def save(settings: Settings) -> None:
    """Persist settings to config.json, creating the file if needed."""
    settings.validate()
    with open(_config_path(), "w", encoding="utf-8") as fh:
        json.dump(asdict(settings), fh, indent=2)
