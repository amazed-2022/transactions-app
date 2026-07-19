#=================================================
# IMPORT
#=================================================
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum, StrEnum


#=================================================
# CLASSES
#=================================================
class Bank(StrEnum):
    EXAMPLE = "ExampleBank"
    KH = "K&H"
    OTP = "OTP"


class CSVFormat:
    def __init__(
        self,
        bank: Bank,
        date_col: str,
        type_col: str,
        partner_col: str,
        amount_col: str,
        currency_col: str,
        message_col: str,
    ):
        self.bank = bank
        self.date_col = date_col
        self.type_col = type_col
        self.partner_col = partner_col
        self.amount_col = amount_col
        self.currency_col = currency_col
        self.message_col = message_col


class Direction(StrEnum):
    IN = "IN"
    OUT = "OUT"


class ChartMode(StrEnum):
    PIE = "pie"
    LINE = "line"


class TimeRange(Enum):
    TEN_YEARS = ("Last 10 years", 120)
    FIVE_YEARS = ("Last 5 years", 60)
    THREE_YEARS = ("Last 3 years", 36)
    TWO_YEARS = ("Last 2 years", 24)
    ONE_AND_HALF_YEAR = ("Last 1.5 year", 18)
    ONE_YEAR = ("Last 1 year", 12)
    SIX_MONTHS = ("Last 6 months", 6)
    THREE_MONTHS = ("Last 3 months", 3)
    ONE_MONTHS = ("Last month", 1)

    @property
    def label(self) -> str:
        return self.value[0]

    @property
    def months(self) -> int:
        return self.value[1]


class Category(StrEnum):
    BANK_FEES = "Bank fees"
    CASH = "Cash"
    SALARY = "Salary"
    PENSION_FUND = "Pension fund"
    LOAN_REPAY = "Loan repayment"
    LOAN_PREPAY = "Loan prepayment"
    MAJOR_EXPENSES = "Major expenses"
    INTERNAL_TRANSFER = "Internal transfer"

    CHILDREN = "Children"
    GROCERIES = "Groceries"
    DRUG_STORE = "Drug store"
    PHARMACY = "Pharmacy"
    PARCELS = "Parcels"
    HOUSEHOLD = "Household"
    CLOTHES = "Clothes"
    TECH = "Tech"
    HOBBY = "Hobby"

    HOLIDAY = "Holiday"
    RESTAURANT = "Restaurant"
    FUEL = "Fuel"
    CAR = "Car"
    GCC = "gcc"

    TRANSPORT = "Transport"
    UTILITIES = "Utilities"
    ENTERTAINMENT = "Entertainment"

    HEALTH = "Health"
    INSURANCE = "Insurance"
    WORK_MEALS = "Work meals"

    OTHER = "Other"
    REFUNDED = "Refunded"
    UNKNOWN = "Unknown"


class Partner(StrEnum):
    ALDI = "ALDI"
    LIDL = "Lidl"
    SPAR = "SPAR"
    CBA = "CBA"

    MULLER_GROUP = "Müller"
    DM_GROUP = "DM"

    OBI_GROUP = "OBI"
    IKEA = "IKEA"
    PRAKTIKER = "PRAKTIKER"

    DECATHLON = "Decathlon"
    OMV = "OMV"
    TELEKOM = "TelekomFelt"

    UNKNOWN = "Unknown"

    @property
    def is_group(self) -> bool:
        return self in {
            Partner.DM_GROUP,
            Partner.MULLER_GROUP,
            Partner.OBI_GROUP,
        }


def get_partner_dropdown_items() -> list[Partner]:
    return [
        p
        for p in Partner
        if p is not Partner.UNKNOWN
    ]


@dataclass(kw_only=True)
class Transaction:
    tx_id: str
    bank: Bank

    booking_date: date
    tx_type: str
    partner_raw: str
    partner: Partner = Partner.UNKNOWN
    amount: Decimal
    currency: str
    direction: Direction
    message: str = ""
    note: str = ""

    category: Category = Category.UNKNOWN
    is_category_overridden: bool = False


@dataclass
class DashboardState:
    bank: Bank | None = None
    partner: Partner | None = None
    category: Category | None = None

    year: int | None = None
    time_range: TimeRange | None = None

    include_major_expenses: bool = False
    include_loan_repay: bool = True
    include_loan_prepay: bool = False
    include_salary: bool = False

    hide_largest_category: bool = False
    monthly_average: bool = False
