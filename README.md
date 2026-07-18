# transactions-app
Simple Python desktop application to import bank CSV exports, categorize transactions, and analyze personal finances.

**Current version:** v1.0.0  
**License:** GNU GPL v3.0  
**Author:** amazed  
**Version history:** [Changelog](#changelog)

---
**Dependencies:**  
- **PySide6**
  - Website: https://www.qt.io/qt-for-python
  - License: LGPL v3.0
- **python-dateutil**
  - Website: https://dateutil.readthedocs.io/
  - License: Apache 2.0
---

## Introduction

A local desktop application for analyzing personal transaction data (all data remains local and no banking connection or online service is required).

The application imports CSV files, automatically categorizes transactions, supports manual overrides, and provides filtering, charts, and statistics for spending analysis.

---
## Installation

1. **Install dependencies**: `pip install PySide6 python-dateutil`
2. Run: `python transactions-app.py`

---


## Features
- CSV import (semicolon-separated, EU number format)
- Automatic category assignment (rule-based)
- Manual category overrides (saved in JSON)
- Expense/income separation
- Interactive filtering by bank, partner, category, year, or rolling time range
- Pie chart by spending category (clickable slices)
- Monthly expense line chart
- Monthly totals and averages
- Transaction table with sorting
- CSV export of the filtered transaction list
  
---

## Usage
1. Download a transaction list in CSV format from your online banking portal
    - supported delimiter: `";"`
    - supported date formats:
      - 2025.12.31
      - 2025-12-31
      - 2025-12-31 14:30:45
      - 12/31/2025
2. Create your own Bank format in `config.py` to correctly detect CSV headers:

  ```python
  KNOWN_BANK_FORMATS: list[CSVFormat] = [
      CSVFormat(
          bank=Bank.MY_BANK,
          date_col="MyDateColumn",
          type_col="MyTypeColumn",
          partner_col="MyPartnerColumn",
          amount_col="MyAmountColumn",
          currency_col="MyCurrencyColumn",
          message_col="MyMessageColumn",
      ),
  ]
  ```
  - Add your bank to `Bank` enum in `models.py`
    ```python
    class Bank(StrEnum):
      EXAMPLE = "ExampleBank"
      MY_BANK = "MyBank"
    ```
3. Start `transactions-app.py` and select your CSV
<img width="402" height="332" alt="image" src="https://github.com/user-attachments/assets/c725dacf-4a51-4d9e-8c45-19a714f3802f" />

GUI
<img width="1802" height="1032" alt="image" src="https://github.com/user-attachments/assets/3e0becad-705c-47a1-8aa8-47909f551944" />

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

---

# Changelog

## [1.0.0] – 2026-07

### Added
- Initial stable release
- Multi-bank CSV import and transaction categorization
- Persistent category overrides
- Filtering, charts, statistics, and sortable transaction table
- CSV export support

### Architecture
- Introduced `TxManager` to centralize transaction processing, filtering, grouping, and statistics
- Introduced `DashboardState` to centralize UI filter and checkbox handling
