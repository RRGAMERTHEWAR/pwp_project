# Customer Billing System

A desktop billing system for a small store built in Python with
**CustomTkinter** (modern GUI) and **SQLite** (storage), plus **fpdf2** (PDF
export) and **matplotlib** (sales charts).

Built as a structured, modular upgrade of the YouTube tutorial
*"How to Create a Customer Billing System in Python"* by [TechXCode](https://www.youtube.com/@TechXCode)
([video](https://www.youtube.com/watch?v=7BwJq81gZMg)).

## Features

- **Login & roles** — Cashiers can create bills and search history; Admins
  additionally manage inventory, analytics, settings and users.
- **Inventory & products** — products table (`name`, `price`, `stock`); line
  items are picked from a searchable dropdown that auto-fills the price.
  Completing a bill deducts stock automatically.
- **Customer lookup by phone** — entering a phone number auto-fills the
  customer's name/email and shows their loyalty balance.
- **Loyalty points & redemption** — 1 point per full 100 currency units earned;
  returning customers can spend accumulated points for a discount on a bill.
- **Live totals** — subtotal, tiered discount, loyalty redemption, tax, loyalty
  points and grand total update on demand.
- **Receipt** — formatted receipt with **Save to database**, **Print** and
  **Export to PDF** (fpdf2, Unicode fonts for ₹).
- **Bill history search** — filter bills by date range, customer name or phone;
  export results to **CSV** (bill-level or item-level for accounting) or **PDF**.
- **Sales dashboard** — day/week/month revenue summary plus matplotlib charts:
  daily revenue (30 days), top-selling items and top customers.
- **Settings** — store name, currency, tax rate, discount tiers and loyalty
  rules editable by an admin and persisted to `config.json`; user management
  (add / delete / change role / reset password) from the same screen.

## Setup

Requires Python 3.10+.

```bash
cd "C:\Users\RATAN\Desktop\pwp_project"
python -m pip install -r requirements.txt
python main.py
```

On Debian/Ubuntu, Tkinter is sometimes a separate package:

```bash
sudo apt install python3-tk
```

## Default accounts

Created automatically on first run (change them from **Settings → Users**):

| Username | Password  | Role    |
|----------|-----------|---------|
| `admin`  | `admin123`| Admin   |
| `cashier`| `cash123` | Cashier |

## What each role can do

| Screen      | Cashier | Admin |
|-------------|:-------:|:-----:|
| Billing     | ✅      | ✅    |
| History     | ✅      | ✅    |
| Inventory   | —       | ✅    |
| Analytics   | —       | ✅    |
| Settings    | —       | ✅    |

## Project layout

```
pwp_project/
├── main.py                  # entry point (login window)
├── billing_system.db        # SQLite DB (auto-created/migrated on first run)
├── config.json              # store settings (created by Settings screen)
├── requirements.txt
├── README.md
├── core/
│   ├── calculations.py      # pure math: discount, tax, loyalty, redemption
│   ├── settings.py          # config.json load/save + validation
│   └── pdfexport.py         # fpdf2 receipt + history PDF export
├── db/
│   └── database.py          # schema, migrations, products/users/search/analytics
└── ui/
    ├── login_view.py        # authentication screen
    ├── app.py               # main window + role-based navigation
    ├── billing_view.py      # customer + product line items + redemption
    ├── receipt_view.py      # receipt + save / print / PDF
    ├── product_view.py      # inventory management (admin)
    ├── history_view.py      # searchable bills + CSV/PDF export
    ├── analytics_view.py    # matplotlib dashboard (admin)
    └── settings_view.py     # business rules + user management (admin)
```

## Verifying the math

From the project root:

```bash
python -c "from core.calculations import Bill, LineItem; \
b=Bill.from_items(customer={'name':'Ratan'}, items=[LineItem('Item A', 3, 1500.0)]); \
print(b.subtotal, b.discount, b.tax, b.loyalty_points, b.total)"
```

Expected for one item @ 3 × ₹1500 (default 5% tax, 5%/10% tiers):

- subtotal = 4500.00
- discount = 225.00 (5% tier)
- tax = 213.75 (5% on 4275.00)
- loyalty_points = 44 (4475.00 // 100 = 44)
- total = 4488.75