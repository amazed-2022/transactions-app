#=================================================
# IMPORT
#=================================================
import csv

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from models import CSVFormat, Direction, Transaction
from config import KNOWN_BANK_FORMATS


#=================================================
# FUNCTIONS
#=================================================
def detect_format(headers: list[str]) -> CSVFormat:
    header_set = {h.strip() for h in headers}

    for fmt in KNOWN_BANK_FORMATS:
        required = {
            fmt.date_col,
            fmt.type_col,
            fmt.partner_col,
            fmt.amount_col,
            fmt.currency_col,
            fmt.message_col,
        }

        if required.issubset(header_set):
            return fmt

    raise ValueError("Unknown CSV format")


def parse_decimal(value: str) -> Decimal:
    if not value:
        return Decimal("0")

    value = value.strip().replace(",", ".")
    return Decimal(value)


def parse_date(value: str):
    for fmt in (
            "%Y.%m.%d",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
            "%m/%d/%Y"
    ):
        try:
            dt = datetime.strptime(value, fmt)
            # return only the date part
            return dt.date()
        except ValueError:
            pass
    raise ValueError(f"Unknown date format: {value}")


def safe_get(row, col):
    return (row.get(col) or "").strip() if col else ""


def read_transactions(path: Path) -> tuple[list[Transaction], str]:
    transactions: list[Transaction] = []
    format_name: str = ""

    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        headers = list(reader.fieldnames or [])

        # get CSV format based on header
        try:
            csv_fmt = detect_format(headers)
            format_name = csv_fmt.bank
        except ValueError as e:
            raise ValueError(
                f"Unsupported CSV file format: {path.name}"
            ) from e

        for row in reader:
            date_str = safe_get(row, csv_fmt.date_col)

            # use type as fallback value for partner
            tx_type = safe_get(row, csv_fmt.type_col) or "Unknown"
            partner_raw = safe_get(row, csv_fmt.partner_col) or tx_type
            amount = parse_decimal(safe_get(row, csv_fmt.amount_col) or "0")
            currency = safe_get(row, csv_fmt.currency_col)
            direction = Direction.IN if amount > 0 else Direction.OUT
            tx_message = safe_get(row, csv_fmt.message_col)

            tx = Transaction(
                bank=csv_fmt.bank,
                booking_date=parse_date(date_str),
                tx_type=tx_type,
                partner_raw=partner_raw,
                amount=amount,
                currency=currency,
                direction=direction,
                message=tx_message,
                tx_id=""
            )

            # generate ID for this istance
            tx.tx_id = f"{tx.bank}|{tx.booking_date}|{tx.partner_raw}|{tx.amount}"

            transactions.append(tx)

    return transactions, format_name
