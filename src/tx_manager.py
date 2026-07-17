#=================================================
# IMPORT
#=================================================
from dataclasses import dataclass
from dateutil.relativedelta import relativedelta
from decimal import Decimal
import re

from models import Category, DashboardState, Direction, Partner, TimeRange, Transaction
from override_service import TxCategoryOverrideService
from config import (
    PARTNER_RULES,
    PARTNER_ALIASES,
    HIGH_PRIO_MESSAGE_RULES,
    LOW_PRIO_PARTNER_RULES,
)

#=================================================
# CLASSES
#=================================================
@dataclass(frozen=True)
class TxStats:
    total: Decimal
    monthly_average: Decimal


class TxManager:
    INCOMPLETE_MONTH_THRESHOLD_DAY = 25

    def __init__(
        self,
        category_overrides: TxCategoryOverrideService,
    ):
        self.category_overrides = category_overrides

        # raw transaction list loaded from CSV file
        self.transactions: list[Transaction] = []

        # cached indexes for fast access
        self.transactions_by_id: dict[str, Transaction] = {}
        self.transactions_by_year: dict[int, list[Transaction]] = {}

    #=================================================
    # properties
    #=================================================
    @property
    def has_transactions(self) -> bool:
        return len(self.transactions) > 0

    @property
    def last_month_is_incomplete(self) -> bool:
        if not self.transactions:
            return False

        last_tx_date = max(tx.booking_date for tx in self.transactions)
        return last_tx_date.day < self.INCOMPLETE_MONTH_THRESHOLD_DAY

    @property
    def available_years(self) -> list[int]:
        return sorted(self.transactions_by_year.keys(), reverse=True)

    @property
    def available_categories(self) -> list[Category]:
        return sorted(
            {tx.category for tx in self.transactions},
            key=lambda c: c.value
        )

    #=================================================
    # normalization / classification
    #=================================================
    @staticmethod
    def resolve_partner(raw: str) -> Partner:
        raw_cf = raw.casefold()

        # check explicit aliases first
        for alias, partner in PARTNER_ALIASES.items():
            pattern = re.escape(alias.casefold())

            if re.search(rf"(^|[\W_]){pattern}([\W_]|$)", raw_cf):
                return partner

        # check direct enum partners
        for partner in Partner:
            if partner.is_group or partner == Partner.UNKNOWN:
                continue

            pattern = re.escape(partner.value.casefold())

            if re.search(rf"(^|[\W_]){pattern}([\W_]|$)", raw_cf):
                return partner

        return Partner.UNKNOWN

    @staticmethod
    def auto_categorize(tx: Transaction) -> Category:
        # structured match first
        if tx.partner != Partner.UNKNOWN:
            return PARTNER_RULES.get(tx.partner, Category.UNKNOWN)

        # fallback to raw rules
        tx_type = tx.tx_type.casefold()
        partner_raw = tx.partner_raw.casefold()
        message = tx.message.casefold()

        # check high-priority rules before general rules
        for keyword, category in HIGH_PRIO_MESSAGE_RULES.items():
            if keyword.casefold() in message:
                return category

        # check low-prio rules in transfer type and partner field
        for keyword, category in LOW_PRIO_PARTNER_RULES.items():
            if keyword.casefold() in tx_type or keyword.casefold() in partner_raw:
                return category

        return Category.UNKNOWN

    #=================================================
    # main processing
    #=================================================
    def process_transactions(self, txs: list[Transaction]) -> int:
        if not txs:
            return 0

        overridden_count = 0

        for tx in txs:
            # normalize partner_raw into Partner enum
            tx.partner = self.resolve_partner(tx.partner_raw)

            # apply category rules, check overrides
            auto = self.auto_categorize(tx)
            override_data = self.category_overrides.get(tx.tx_id, auto)
            tx.category, tx.is_category_overridden, tx.note = override_data

            if tx.is_category_overridden:
                overridden_count += 1

            # update the fast lookup table
            self.transactions_by_id[tx.tx_id] = tx

        # add them to the main list
        self.transactions.extend(txs)

        self.transactions.sort(
            key=lambda t: t.booking_date,
            reverse=True
        )
        self._rebuild_year_index()

        return overridden_count

    def _rebuild_year_index(self) -> None:
        # build internal year lookup
        self.transactions_by_year = self.group_by_year(self.transactions)

    #=================================================
    # main grouping
    #=================================================
    @staticmethod
    def group_by_year(
        txs: list[Transaction],
    ) -> dict[int, list[Transaction]]:
        grouped: dict[int, list[Transaction]] = {}

        for tx in txs:
            key = tx.booking_date.year
            grouped.setdefault(key, []).append(tx)

        return grouped

    @staticmethod
    def group_by_category(
        txs: list[Transaction],
    ) -> dict[Category, list[Transaction]]:
        grouped: dict[Category, list[Transaction]] = {}

        for tx in txs:
            grouped.setdefault(tx.category, []).append(tx)

        return grouped

    @staticmethod
    def group_by_month(
        txs: list[Transaction],
    ) -> dict[str, list[Transaction]]:
        grouped: dict[str, list[Transaction]] = {}

        for tx in txs:
            key = f"{tx.booking_date.year}-{tx.booking_date.month:02d}"
            grouped.setdefault(key, []).append(tx)

        return grouped

    #=================================================
    # queries
    #=================================================
    def get_transactions_for_year(
        self,
        year: int | None,
    ) -> list[Transaction]:

        if year is None:
            return self.transactions

        return self.transactions_by_year.get(year, [])

    def get_transactions_for_time_range(
        self,
        time_range: TimeRange
    ) -> list[Transaction]:

        # ALL case
        if time_range is None:
            return self.transactions

        if not self.transactions:
            return []

        # latest transaction date
        last_date = max(tx.booking_date for tx in self.transactions)

        # start of the selected calendar-month period
        # last_date.replace(day=1) does not modify last_date
        start = (
            last_date.replace(day=1)
            - relativedelta(months=time_range.months - 1)
        )

        # filter to the selected period
        return [
            tx
            for tx in self.transactions
            if start <= tx.booking_date <= last_date
        ]

    def get_filtered_transactions(
        self,
        state: DashboardState,
        *,
        use_category_filter: bool = True,
    ) -> list[Transaction]:

        # filter based on year / range selection
        if state.year is not None:
            txs = self.get_transactions_for_year(state.year)
        elif state.time_range is not None:
            txs = self.get_transactions_for_time_range(state.time_range)
        else:
            txs = self.transactions

        if state.bank is not None:
            txs = [tx for tx in txs if tx.bank == state.bank]

        if state.partner is not None:
            txs = [tx for tx in txs if tx.partner == state.partner]

        if use_category_filter and state.category is not None:
            txs = [tx for tx in txs if tx.category == state.category]

        return txs

    def get_history_months(self) -> list[str]:
        return sorted({
            f"{tx.booking_date.year}-{tx.booking_date.month:02d}"
            for tx in self.transactions
        })

    def get_available_time_ranges(self) -> list[TimeRange]:
        max_months = self.count_active_months(self.transactions)

        return [
            r for r in TimeRange
            if r.months <= max_months
        ]

    #=================================================
    # category overrides
    #=================================================
    def override_transaction_category(
        self,
        tx: Transaction,
        category: Category,
        note: str,
    ) -> None:

        # store the override data
        self.category_overrides.set(tx.tx_id, category, note)

        tx.is_category_overridden = True
        tx.category = category
        tx.note = note

    #=================================================
    # time logic
    #=================================================
    def resolve_month_span(
        self,
        state: DashboardState,
    ) -> int:

        if state.year is not None:
            year_txs = self.get_transactions_for_year(state.year)
            return self.count_active_months(year_txs)

        if state.time_range is not None:
            return state.time_range.months

        # count with the whole span
        return self.count_active_months(self.transactions)

    @staticmethod
    def count_active_months(
            txs: list[Transaction]
    ) -> int:
        return len({
            (tx.booking_date.year, tx.booking_date.month)
            for tx in txs
        })

    @staticmethod
    def exclude_incomplete_last_month(
        txs: list[Transaction],
    ) -> tuple[list[Transaction], int]:
        if not txs:
            return txs, 0

        last_date = max(tx.booking_date for tx in txs)

        # latest month is incomplete
        if last_date.day < 25:
            complete_txs = [
                tx
                for tx in txs
                if (
                    tx.booking_date.year != last_date.year
                    or tx.booking_date.month != last_date.month
                )
            ]

            removed_count = len(txs) - len(complete_txs)
            return complete_txs, removed_count

        return txs, 0

    #=================================================
    # basic filters
    #=================================================
    @staticmethod
    def outgoing_transactions(txs: list[Transaction]) -> list[Transaction]:
        return [
            tx for tx in txs
            if tx.direction == Direction.OUT
        ]

    @staticmethod
    def exclude_categories(
            txs: list[Transaction],
            categories: set[Category],
    ) -> list[Transaction]:
        return [
            tx
            for tx in txs
            if tx.category not in categories
        ]

    @staticmethod
    def transactions_in_category(
            txs: list[Transaction],
            category: Category,
    ) -> list[Transaction]:
        return [
            tx
            for tx in txs
            if tx.category == category
        ]

    #=================================================
    # chart logic
    #=================================================
    def pie_chart_transactions(
            self,
            state: DashboardState,
    ) -> list[Transaction]:

        txs = self.get_filtered_transactions(
            state,
            use_category_filter=False,
        )

        txs = self.chart_transactions(txs, state)

        if state.hide_largest_category:
            txs = self.exclude_largest_category(txs)

        return txs

    def line_chart_transactions(
            self,
            txs: list[Transaction],
            state: DashboardState,
    ) -> list[Transaction]:
        txs = self.chart_transactions(txs, state)

        if state.category is None:
            txs = self.exclude_categories(txs, {Category.SALARY})

        return txs

    @staticmethod
    def chart_transactions(
            txs: list[Transaction],
            state: DashboardState,
    ) -> list[Transaction]:

        exceptions = {
            Category.INTERNAL_TRANSFER,
            Category.REFUNDED
        }

        if not state.include_major_expenses:
            exceptions.add(Category.MAJOR_EXPENSES)

        if not state.include_loan_repay:
            exceptions.add(Category.LOAN_REPAY)

        if not state.include_loan_prepay:
            exceptions.add(Category.LOAN_PREPAY)

        # allow the incoming salary category when requested
        def passes_direction_filter(tx: Transaction) -> bool:
            return (
                tx.direction == Direction.OUT
                or (state.include_salary and tx.category == Category.SALARY)
            )

        # include explicitly selected category, but keep other exclusions hidden
        if state.category in exceptions:
            return [
                tx
                for tx in txs
                if passes_direction_filter(tx)
                and (
                   tx.category == state.category
                   or tx.category not in exceptions
                )
            ]

        # filter them out otherwise
        return [
            tx
            for tx in txs
            if passes_direction_filter(tx)
            and tx.category not in exceptions
        ]

    @staticmethod
    def exclude_largest_category(
        txs: list[Transaction],
    ) -> list[Transaction]:
        category_totals = TxManager.category_totals(txs)

        if len(category_totals) <= 1:
            return txs

        largest_category = max(
            category_totals,
            key=lambda category: category_totals[category]
        )

        return [
            tx
            for tx in txs
            if tx.category != largest_category
        ]

    #=================================================
    # basic aggregations
    #=================================================
    @staticmethod
    def total_amount(txs: list[Transaction]) -> Decimal:
        return sum((abs(tx.amount) for tx in txs), Decimal("0"))

    @staticmethod
    def category_totals(txs: list[Transaction]) -> dict[Category, Decimal]:
        totals: dict[Category, Decimal] = {}

        for tx in txs:
            # key will be the category value (e.g. "Groceries")
            key = tx.category
            totals[key] = totals.get(key, Decimal("0")) + abs(tx.amount)

        return totals

    @staticmethod
    def monthly_stats(txs: list[Transaction], months: int) -> TxStats:
        total = TxManager.total_amount(txs)
        avg = total / months if months > 0 else Decimal("0")

        return TxStats(
            total=total,
            monthly_average=avg
        )

    @staticmethod
    def category_monthly_stats(
        txs: list[Transaction],
        months: int
    ) -> dict[Category, TxStats]:
        grouped: dict[Category, list[Transaction]] = {}

        for tx in txs:
            grouped.setdefault(tx.category, []).append(tx)

        return {
            cat: TxManager.monthly_stats(items, months)
            for cat, items in grouped.items()
        }

    @staticmethod
    def category_monthly_averages(
            txs: list[Transaction],
            months: int
    ) -> dict[Category, Decimal]:

        totals = TxManager.category_totals(txs)

        if months <= 0:
            return {
                cat: Decimal("0")
                for cat in totals
            }

        return {
            cat: total / months
            for cat, total in totals.items()
        }
