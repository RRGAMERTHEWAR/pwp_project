# 🧭 Quick Guide: How to Understand & Edit This Project

Welcome! This guide explains how this Point-of-Sale (POS) & Billing System is structured, how the data flows, and exactly where to make common changes.

---

## 📁 1. Project Map (Where Things Live)

```text
pwp_project/
├── main.py                  # 🚀 Starting point: verifies dependencies, initializes DB, and opens login
├── config.json              # ⚙️ App settings (tax rates, discounts, store name, currency)
├── billing_system.db        # 🗄️ SQLite database (stores products, bills, users, customers)
│
├── core/                    # 🧠 Business Logic (Calculations, Config, Helpers)
│   ├── calculations.py      # Computes tax, discount tiers, loyalty points, and grand totals
│   ├── settings.py          # Reads and writes config.json
│   ├── pdfexport.py         # Generates PDF receipts using fpdf2
│   ├── backup.py            # Backup and restore database utility
│   ├── logger.py            # Records errors and info to app.log
│   └── admin.py             # CLI admin utilities
│
├── db/                      # 💾 Database Operations (Raw SQL queries)
│   └── database.py          # Creates tables, adds/edits products, saves bills, checks logins
│
└── ui/                      # 🖥️ User Interface (CustomTkinter screens)
    ├── theme.py             # Colors, fonts, and visual styles (Change look & feel here!)
    ├── login_view.py        # Login pop-up / user authentication screen
    ├── app.py               # Main window: sidebar navigation, header, and role permissions
    ├── billing_view.py      # Core billing screen (adding items, customer details, live calculations)
    ├── product_view.py      # Manage inventory (add, edit, delete products & stock)
    ├── receipt_view.py      # Shows receipt preview, printing, and PDF export
    ├── history_view.py      # Search past bills and export reports to CSV/PDF
    ├── analytics_view.py    # Visual sales charts (matplotlib) & revenue summary
    ├── settings_view.py     # Settings screen (taxes, store name, user management)
    └── customer_view.py     # View and manage customer profiles & loyalty points
```

---

## 🔄 2. How the App Works (Execution Flow)

1. **Launch (`main.py`)**:
   - Checks if required libraries (`customtkinter`, `fpdf2`, `matplotlib`) are installed.
   - Calls `database.init_db()` to create SQLite tables if they do not exist.
   - Launches `LoginWindow` in [login_view.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/login_view.py).

2. **Login (`ui/login_view.py`)**:
   - Takes username & password.
   - Calls `database.verify_login()`.
   - On success, destroys itself and launches `BillingApp` in [app.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/app.py) passing the logged-in user profile.

3. **Main Dashboard (`ui/app.py`)**:
   - Builds the sidebar tabs: **Billing**, **History**, **Inventory**, **Customers**, **Analytics**, **Settings**.
   - If the user is a `cashier`, management tabs (Inventory, Settings, Analytics) are hidden automatically.

4. **Making a Bill (`ui/billing_view.py`)**:
   - Cashier enters customer phone $\rightarrow$ looks up existing customer in DB.
   - Cashier picks product & quantity $\rightarrow$ adds to item table.
   - Automatically calls functions in [calculations.py](file:///c:/Users/RATAN/Desktop/pwp_project/core/calculations.py) to compute subtotal, discounts, and taxes.
   - Clicking "Generate Bill" saves to `billing_system.db`, deducts inventory stock, and renders the receipt in [receipt_view.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/receipt_view.py).

---

## 🛠️ 3. Quick "How Do I Edit..." Cheat Sheet

| I want to change... | Which file to edit? | Key function or variable |
| :--- | :--- | :--- |
| **Colors, fonts, or window theme** | [ui/theme.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/theme.py) | Edit the color hex codes like `PRIMARY`, `BG_DARK`, `TEXT_MAIN` |
| **Currency symbol or Store Name** | [config.json](file:///c:/Users/RATAN/Desktop/pwp_project/config.json) or [ui/settings_view.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/settings_view.py) | Change `"currency"` (e.g. `"$"` or `"₹"`) or `"store_name"` |
| **Default demo accounts / Login UI**| [ui/login_view.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/login_view.py) | Search for `_set_creds` or adjust `_ROLE_DESCRIPTION` |
| **Tax calculation or Discount tiers**| [core/calculations.py](file:///c:/Users/RATAN/Desktop/pwp_project/core/calculations.py) | `compute_tax()`, `compute_discount()`, `compute_bill_totals()` |
| **Receipt appearance or text** | [ui/receipt_view.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/receipt_view.py) and [core/pdfexport.py](file:///c:/Users/RATAN/Desktop/pwp_project/core/pdfexport.py) | `render_receipt_text()` or PDF styling in `PDFReceipt` |
| **Database columns or tables** | [db/database.py](file:///c:/Users/RATAN/Desktop/pwp_project/db/database.py) | `init_db()` (SQL table schemas) |
| **Sales chart styles or time ranges**| [ui/analytics_view.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/analytics_view.py) | Look at `_draw_daily_chart()` or `_draw_top_items()` |

---

## 💡 4. Best Practices When Editing

1. **Keep UI separate from SQL**:
   - Don't write raw SQL inside `ui/` files.
   - Always put SQL queries into [db/database.py](file:///c:/Users/RATAN/Desktop/pwp_project/db/database.py) and call the function from the UI.
2. **Use `theme.py` for styling**:
   - Avoid hardcoding random hex colors across files. Import them from [ui/theme.py](file:///c:/Users/RATAN/Desktop/pwp_project/ui/theme.py) to keep dark/light modes consistent.
3. **Check the logs**:
   - If an error occurs, look at `app.log` in the root folder to see the exact traceback.

