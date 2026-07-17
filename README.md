# transactions-app
Simple Python desktop application to import bank CSV exports, categorize transactions, and analyze personal finances.

**Current version:** v1.0.0  
**License:** GNU GPL v3.0  
**Author:** amazed  
**Version history:** 

---

## Features
- CSV import (semicolon-separated, EU number format)
- Automatic category assignment (rule-based)
- Manual category overrides (saved in JSON)
- Expense/income separation
- Interactive filtering by bank, partner, category, year, or rolling time range
- Pie chart by spending category
- Monthly expense line chart
- Monthly totals and averages
- Transaction table with sorting
- CSV export of the filtered transaction list

---

## Dependencies

**PySide6**
- Website: https://www.qt.io/qt-for-python
- License: LGPL v3.0

**python-dateutil**
- Website: https://dateutil.readthedocs.io/
- License: Apache 2.0

---

## Introduction

A local desktop application for analyzing personal transaction data.

The application imports CSV files, automatically categorizes transactions, supports manual overrides, and provides filtering, charts, and statistics for spending analysis.

All data remains local and no banking connection or online service is required.

---

## Installation

Install dependencies:

    pip install PySide6 python-dateutil

Run:

    python main.py

---

## Overrides

Manual category corrections can be stored in:

    overrides.json

Example:

    {
        "transaction-id": {
            "category": "Groceries",
            "note": "Manual correction"
        }
    }

Add to `.gitignore`:

    # User config
    overrides.json

---

## Privacy

- No cloud services
- No bank API connection
- No accounts required
- No data uploads

All transaction data stays on the local machine.

---

## License

This project is licensed under the **GNU General Public License v3.0 (GPL-3.0)**.

Copyright (C) amazed 2026.
