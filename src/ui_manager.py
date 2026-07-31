#=================================================
# IMPORT
#=================================================
import csv
import math

from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal
from typing import Any, cast

from models import (
    Bank, Category, ChartMode, Direction, Transaction, DashboardState,
    get_partner_dropdown_items
)
from tx_manager import TxManager

from PySide6.QtCharts import QCategoryAxis, QChart, QLineSeries, QPieSeries, QValueAxis
from PySide6.QtCore import Qt, QModelIndex, QObject, QSignalBlocker
from PySide6.QtGui import (
    QBrush, QColor, QStandardItem, QStandardItemModel
)
from PySide6.QtWidgets import (
    QApplication, QComboBox, QHeaderView, QInputDialog, QProgressDialog
)

#=================================================
# TABLE DEFINITIONS
#=================================================
def get_bank(tx): return tx.bank
def get_date(tx): return tx.booking_date.strftime("%Y-%m-%d")
def get_partner(tx): return tx.partner_raw
def get_amount(tx): return int(tx.amount)
def get_currency(tx): return tx.currency
def get_category(tx): return tx.category.value
def get_direction(tx): return tx.direction.value
def get_note(tx): return tx.note

TABLE_COLUMNS = [
    {"key": "bank", "name": "Bank", "width": 80, "align": "center", "getter": get_bank},
    {"key": "date", "name": "Date", "width": 80, "align": "center", "getter": get_date},
    {"key": "partner", "name": "Partner", "width": 180, "align": "left", "getter": get_partner},
    {"key": "amount", "name": "Amount", "width": 80, "align": "right", "getter": get_amount},
    {"key": "currency", "name": "Currency", "width": 80, "align": "left", "getter": get_currency},
    {"key": "category", "name": "Category", "width": 100, "align": "center", "getter": get_category},
    {"key": "note", "name": "Note", "width": 120, "align": "center", "getter": get_note},
    # {"key": "direction", "name": "Direction", "width": 80, "align": "center", "getter": get_direction},
]

# tell the type checker, this is a str
TABLE_HEADERS = [cast(str, c["name"]) for c in TABLE_COLUMNS]
COLUMN_INDEX = {c["key"]: i for i, c in enumerate(TABLE_COLUMNS)}
CATEGORY_COL = COLUMN_INDEX["category"]
Q_STD_ITEM_SORT_ROLE = Qt.ItemDataRole.UserRole + 1

#=================================================
# UI Manager
#=================================================
class UIManager:
    def __init__(self, window, transaction_manager: TxManager):
        # window type is MainWindow, store reference to passed instance
        self.ui = window
        self.tx_manager = transaction_manager
        self.txs_to_export: list[Transaction] = []

        # helpers
        self._table_sort_column = COLUMN_INDEX["date"]
        self._table_sort_order = Qt.SortOrder.DescendingOrder
        self._last_logged_tx: str | None = None
        self._table_month_rows: dict[str, list[int]] = {}
        self._chart_months: list[str] = []
        self._chart_values: dict[str, Decimal] = {}

        self._connect_signals()

    def _connect_signals(self) -> None:
        # only the function reference is bound here (no call operator "()" added)
        # warning appears because PySide6 signals are C++ bindings; .connect() exists at runtime
        self.ui.bank_dropdown.currentIndexChanged.connect(self._on_filter_change)
        self.ui.partner_dropdown.currentIndexChanged.connect(self._on_filter_change)
        self.ui.category_dropdown.currentIndexChanged.connect(self._on_filter_change)
        self.ui.year_dropdown.currentIndexChanged.connect(self._on_filter_change)
        self.ui.time_range_dropdown.currentIndexChanged.connect(self._on_filter_change)

        self.ui.major_expenses_checkbox.stateChanged.connect(self._on_filter_change)
        self.ui.loan_repay_checkbox.stateChanged.connect(self._on_filter_change)
        self.ui.loan_prepay_checkbox.stateChanged.connect(self._on_filter_change)
        self.ui.salary_checkbox.stateChanged.connect(self._on_filter_change)

        self.ui.hide_largest_category_checkbox.stateChanged.connect(self._on_filter_change)
        self.ui.monthly_avg_chart_checkbox.stateChanged.connect(self._on_filter_change)
        self.ui.export_table_button.clicked.connect(self._export_table)

        # Qt emits a bool (checked state) when the toggle changes
        # the lambda receives that emitted value as its first argument
        # and forwards it to the callback together with the sender widget
        self.ui.pie_chart_toggle.toggled.connect(
            lambda checked: self._on_toggle_chart_mode(checked, self.ui.pie_chart_toggle)
        )
        self.ui.line_chart_toggle.toggled.connect(
            lambda checked: self._on_toggle_chart_mode(checked, self.ui.line_chart_toggle)
        )

        # warning appears because PySide6 signals are C++ bindings; .connect() exists at runtime
        self.ui.table_output.clicked.connect(self._on_cell_clicked)

    #=================================================
    # public API
    #=================================================
    def clear_text_output(self) -> None:
        self.ui.text_output.clear()

    def refresh_ui(self) -> None:
        # get current filter state
        state: DashboardState = self.ui.get_dashboard_state()

        # apply chart-specific filters (categories, exclusions, salary)
        pie_txs = self.tx_manager.pie_chart_transactions(state)

        # table includes category filter, line chart uses table data
        table_txs = self.tx_manager.get_filtered_transactions(state)
        line_txs = self.tx_manager.line_chart_transactions(table_txs, state)

        self._build_table(table_txs)
        self._build_chart(
            pie_txs=pie_txs,
            line_txs=line_txs,
            state=state
        )

        # reuse the datasets prepared for line/table
        self._print_statistics(line_txs, state)
        self.txs_to_export = table_txs

    def update_bank_dropdown(self) -> None:
        self._populate_dropdown(
            self.ui.bank_dropdown,
            list(Bank),
            default_label="All banks",
        )

    def update_partner_dropdown(self) -> None:
        partners = sorted(
            get_partner_dropdown_items(),
            key=lambda p: p.value
        )

        self._populate_dropdown(
            self.ui.partner_dropdown,
            partners,
            default_label="All partners",
        )

    def update_category_dropdown(self) -> None:
        self._populate_dropdown(
            self.ui.category_dropdown,
            self.tx_manager.available_categories,
            default_label="All categories",
        )

    def update_year_dropdown(self) -> None:
        self._populate_dropdown(
            self.ui.year_dropdown,
            self.tx_manager.available_years,
            default_label="All years",
            label_attr=None,
        )

    def update_time_range_dropdown(self) -> None:
        ranges = self.tx_manager.get_available_time_ranges()

        self._populate_dropdown(
            self.ui.time_range_dropdown,
            ranges,
            default_label="All time",
            label_attr="label",
        )

    # =================================================
    # internal helpers
    # =================================================
    @staticmethod
    def _get_display_currency(txs: list[Transaction]) -> str:
        currencies = {tx.currency for tx in txs if tx.currency}

        if len(currencies) == 1:
            return currencies.pop()

        return "mixed"

    def _log_stats(
            self,
            txs: list[Transaction],
            months: int,
            title: str | None = None,
    ) -> None:

        stats = self.tx_manager.monthly_stats(txs, months)
        currency = self._get_display_currency(txs)

        formatted_avg = f"{int(stats.monthly_average):,}".replace(",", " ")
        formatted_total = f"{int(stats.total):,}".replace(",", " ")

        if title:
            self.ui.log(title)

        if months > 1:
            self.ui.log(f"Total amount: {formatted_total} {currency}")
            self.ui.log(f"Monthly average: {formatted_avg} {currency}", bold=True)
            self.ui.log(f"Calculation period: {months} months")
        else:
            self.ui.log(f"Amount for the month: {formatted_total} {currency}", bold=True)

    def _print_statistics(
            self,
            stats_txs: list[Transaction],
            state: DashboardState,
    ) -> None:

        # resolve month span handles incomplete months
        months = self.tx_manager.resolve_month_span(state)

        if state.category is not None:
            self._log_stats(
                stats_txs,
                months,
                title=f"Selected category: {state.category}"
            )
            return

        # make sure salary not appears in overall stats
        stats_txs = self.tx_manager.exclude_categories(
            stats_txs,
            {Category.SALARY}
        )

        self._log_stats(
            stats_txs,
            months
        )

        included = []

        if state.include_major_expenses:
            included.append("Major expenses")

        if state.include_loan_prepay:
            included.append("Loan prepayments")

        if included:
            label = (
                "Included special category"
                if len(included) == 1
                else "Included special categories"
            )

            self.ui.log(
                f"{label}: {', '.join(included)}",
                bold=True
            )

    def _export_table(self) -> None:
        export_filename = "transactions_export.csv"

        if not self.txs_to_export:
            self.ui.log("No transactions to export.", color="orange")
            return

        try:
            with open(export_filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)

                writer.writerow(TABLE_HEADERS)

                for tx in self.txs_to_export:
                    writer.writerow(
                        [
                            col["getter"](tx)
                            for col in TABLE_COLUMNS
                        ]
                    )

            self.ui.log(
                f"Exported {len(self.txs_to_export)} transactions to {export_filename}"
            )

        except OSError as e:
            self.ui.log(
                f"Export failed: {e}",
                bold=True,
                color="red"
            )

    @staticmethod
    def _populate_dropdown(
        cb: QComboBox,
        items: list[Any],
        *,
        default_label: str,
        label_attr: str | None = "value",
    ) -> None:

        current_data = cb.currentData()

        with QSignalBlocker(cb):
            cb.clear()
            # default has no member equivalent, store None as its data
            # to help filtering (None means all member)
            cb.addItem(default_label, None)

            # populate dropdown with item attribute
            for item in items:
                label = item if label_attr is None else getattr(item, label_attr)
                cb.addItem(str(label), item)

            # restore previous selection if it still exists
            index = cb.findData(current_data)

            if index >= 0:
                cb.setCurrentIndex(index)
            else:
                cb.setCurrentIndex(0)

    def _sync_category_show_checkboxes(self, category: Category | None) -> None:
        if category == Category.MAJOR_EXPENSES:
            checkbox = self.ui.major_expenses_checkbox
        elif category == Category.SALARY:
            checkbox = self.ui.salary_checkbox
        elif category == Category.LOAN_PREPAY:
            checkbox = self.ui.loan_prepay_checkbox
        else:
            return

        if not checkbox.isChecked():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(True)

    #=================================================
    # event handlers
    #=================================================
    def _on_filter_change(self) -> None:
        self.clear_text_output()
        state: DashboardState = self.ui.get_dashboard_state()

        if state.year is not None and state.time_range is not None:
            self.ui.log(
                "Time range is ignored when a year is selected.",
                bold=True,
                color="orange"
            )

        # sync special category checkboxes
        # QSignalBlocker prevents recursive filter updates
        self._sync_category_show_checkboxes(state.category)

        self.refresh_ui()

    def _on_toggle_chart_mode(self, checked: bool, sender: QObject) -> None:
        pie = self.ui.pie_chart_toggle
        line = self.ui.line_chart_toggle

        def restore(btn):
            if not btn.isChecked():
                with QSignalBlocker(btn):
                    btn.setChecked(True)

        if sender == pie:
            if not checked:
                restore(pie)
                return
            with QSignalBlocker(line):
                line.setChecked(False)
            self.ui.set_chart_mode(ChartMode.PIE)

        elif sender == line:
            if not checked:
                if not line.isChecked():
                    restore(line)
                    return
            with QSignalBlocker(pie):
                pie.setChecked(False)
            self.ui.set_chart_mode(ChartMode.LINE)

        self.clear_text_output()
        self.refresh_ui()

    def _on_cell_clicked(self, index: QModelIndex) -> None:
        row = index.row()
        col = index.column()
        model = self.ui.table_output.model()

        # first column always stores ID
        id_index = model.index(row, 0)
        tx_id = id_index.data(Qt.ItemDataRole.UserRole)

        if not tx_id:
            return

        # get the actual instance
        tx = self.tx_manager.transactions_by_id[tx_id]

        # don't log the same transaction again and again
        if tx_id != self._last_logged_tx:
            self.ui.log(f"Partner: {tx.partner} | {tx.tx_type} | Message: {tx.message}")
            self._last_logged_tx = tx_id

        # only trigger popup when category column is clicked
        if col == CATEGORY_COL:
            if self._open_category_dialog(tx):
                # category may become available after override
                self.update_category_dropdown()
                self.refresh_ui()
            return

    def _open_category_dialog(self, tx: Transaction) -> bool:
        categories = sorted([c for c in Category])
        category_values = [c.value for c in categories]
        category_map = {c.value: c for c in categories}

        # start with current if available
        current_index = 0
        if tx.category in categories:
            current_index = categories.index(tx.category)

        new_category, ok = QInputDialog.getItem(
            self.ui,
            "Change Category",
            "Select new category:",
            category_values,
            current=current_index,
            editable=False
        )

        # check if user canceled
        if not ok:
            return False

        # get back the category enum
        new_cat = category_map[new_category]

        new_note, ok = QInputDialog.getText(
            self.ui,
            "Edit Note",
            "Note:",
            text=tx.note or ""
        )

        if new_cat == tx.category and new_note == tx.note:
            return False

        # apply the new category and note
        self.tx_manager.override_transaction_category(tx, new_cat, new_note)
        return True

    def _on_table_sort_changed(
            self,
            column: int,
            order: Qt.SortOrder
    ) -> None:
        self._table_sort_column = column
        self._table_sort_order = order

    def _on_point_clicked(self, point):

        x = cast(float, point.x())
        index = round(x)

        if index < 0 or index >= len(self._chart_months):
            return

        month = self._chart_months[index]
        value = self._chart_values.get(month)
        currency = self._get_display_currency(self.txs_to_export)

        if value is not None:
            self.clear_text_output()
            formatted = f"{int(value):,}".replace(",", " ")
            self.ui.log(
                f"Selected month: {month}"
            )
            self.ui.log(
                f"Total spending: {formatted} {currency}",
                bold=True,
            )

        # jump table to first transaction in this month
        rows = self._table_month_rows.get(month)
        if not rows:
            return

        row = rows[0]

        model = self.ui.table_output.model()
        index = model.index(row, 0)

        self.ui.table_output.clearSelection()
        self.ui.table_output.selectRow(row)
        self.ui.table_output.scrollTo(
            index,
            self.ui.table_output.ScrollHint.PositionAtTop
        )

    #=================================================
    # table building
    #=================================================
    @contextmanager
    def progress_dialog(self, title: str, maximum: int):
        dialog = QProgressDialog(title, "Cancel", 0, maximum, self.ui)
        dialog.setWindowModality(Qt.WindowModality.WindowModal)
        dialog.setMinimumDuration(0)
        dialog.setAutoClose(True)
        dialog.setAutoReset(True)
        dialog.setValue(0)
        dialog.show()
        try:
            yield dialog
        finally:
            dialog.close()

    def _build_table(self, transactions: list[Transaction]) -> None:
        # clear map
        self._table_month_rows.clear()

        # create new model, start with uncheck checkbox
        model = QStandardItemModel()
        model.setSortRole(Q_STD_ITEM_SORT_ROLE)
        model.setHorizontalHeaderLabels(TABLE_HEADERS)

        month_colors = [
            QColor(245, 245, 245),  # gray
            QColor(235, 245, 255),  # blue tint
            QColor(235, 255, 235),  # green tint
            QColor(255, 245, 235)   # warm peach tint
        ]
        month_to_color: dict[str, QColor] = {}
        next_color = 0

        with self.progress_dialog("Building table...", len(transactions)) as progress:

            for row, tx in enumerate(transactions):
                month_key = tx.booking_date.strftime("%Y-%m")
                if month_key not in month_to_color:
                    month_to_color[month_key] = month_colors[next_color]
                    next_color = (next_color + 1) % len(month_colors)

                items = self._build_row_items(tx, month_to_color[month_key])
                model.appendRow(items)

                # store all rows for this month
                self._table_month_rows.setdefault(month_key, []).append(row)

                if row % 100 == 0:
                    progress.setValue(row)
                    QApplication.processEvents()
                if progress.wasCanceled():
                    break

            progress.setValue(len(transactions))

        self.ui.table_output.setModel(model)
        self.ui.table_output.setSortingEnabled(True)
        self.ui.table_output.clearSelection()

        # re-apply saved table sort after refresh
        self.ui.table_output.sortByColumn(
            self._table_sort_column,
            self._table_sort_order
        )

        header = self.ui.table_output.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # connected handler stores user-selected table sorting
        header.sortIndicatorChanged.connect(self._on_table_sort_changed)

        for i, c in enumerate(TABLE_COLUMNS):
            header.resizeSection(i, c["width"])

        header.setStretchLastSection(True)
        header.setFixedHeight(46)

    @staticmethod
    def _build_row_items(
        tx: Transaction,
        color: QColor | None = None,
    ) -> list[QStandardItem]:

        row_data = [col["getter"](tx) for col in TABLE_COLUMNS]
        items = []

        align_map = {
            "left": Qt.AlignmentFlag.AlignLeft,
            "right": Qt.AlignmentFlag.AlignRight,
            "center": Qt.AlignmentFlag.AlignHCenter,
        }

        for i, value in enumerate(row_data):
            item = QStandardItem()

            if TABLE_COLUMNS[i]["key"] == "date":
                # visible text shown in the table cell
                item.setData(value, Qt.ItemDataRole.DisplayRole)
                # value used for sorting
                item.setData(tx.booking_date.toordinal(), Q_STD_ITEM_SORT_ROLE)
            elif TABLE_COLUMNS[i]["key"] == "amount":
                item.setData(f"{value:,}".replace(",", " "), Qt.ItemDataRole.DisplayRole)
                item.setData(value, Q_STD_ITEM_SORT_ROLE)
            else:
                # visible text shown in the table cell
                item.setData(value, Qt.ItemDataRole.DisplayRole)
                item.setData(value.casefold(), Q_STD_ITEM_SORT_ROLE)

            # hidden identifier used for lookup (app logic)
            # retrieved via row index -> first column
            # (independent of clicked column)
            if i == 0:
                item.setData(tx.tx_id, Qt.ItemDataRole.UserRole)

            # get horizontal alignment form defined map
            align = cast(str, TABLE_COLUMNS[i].get("align", "left"))
            item.setTextAlignment(align_map[align] | Qt.AlignmentFlag.AlignVCenter)
            item.setEditable(False)

            if color:
                item.setBackground(QBrush(color))

            items.append(item)

        # highlight overridden categories
        if tx.is_category_overridden:
            items[COLUMN_INDEX["category"]].setBackground(QBrush(QColor(255, 245, 220)))

        # color income / expense
        amount_col = COLUMN_INDEX["amount"]
        if tx.direction == Direction.IN:
            items[amount_col].setForeground(QBrush(QColor(0, 130, 0)))
        else:
            items[amount_col].setForeground(QBrush(QColor(180, 0, 0)))

        return items

    #=================================================
    # charts
    #=================================================
    def _build_chart(
            self,
            *,
            pie_txs: list[Transaction],
            line_txs: list[Transaction],
            state: DashboardState,
    ) -> None:

        mode = self.ui.get_chart_mode()
        if mode == ChartMode.PIE:
            self._build_pie_chart(pie_txs, state)

        elif mode == ChartMode.LINE:
            self._build_line_chart(line_txs, state)

    def _build_pie_chart(
        self,
        txs: list[Transaction],
        state: DashboardState
    ) -> None:

        # connected to each slice; ensure only one is exploded at a time
        def _on_slice_clicked(cat: Category):
            self.clear_text_output()
            current_state: DashboardState = self.ui.get_dashboard_state()

            if current_state.category == cat:
                self.ui.set_selected_category(None)
                self.clear_text_output()
            else:
                self.ui.set_selected_category(cat)

            self.refresh_ui()

        if state.monthly_average:
            # calculate monthly averages
            month_span = self.tx_manager.resolve_month_span(state)
            category_values = self.tx_manager.category_monthly_averages(
                txs,
                month_span
            )
        else:
            category_values = self.tx_manager.category_totals(txs)

        series = QPieSeries()

        # sort descending by value
        sorted_items = sorted(
            category_values.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # calculate percentage from visible slices only
        total: Decimal = sum(
            (value for _, value in sorted_items),
            Decimal("0")
        )

        if total == 0:
            self.ui.log(
                "Cannot render pie chart without transactions.",
                bold=True,
                color="orange"
            )
            return

        for category, value in sorted_items:
            pie_slice = series.append(category, float(value))
            pie_slice.setExploded(state.category == category)
            pie_slice.setExplodeDistanceFactor(0.2)

            # show percentage + label
            percent = (float(value) / float(total) * 100)
            formatted_value = f"{int(value):,}".replace(",", " ")
            currency = self._get_display_currency(txs)
            pie_slice.setLabel(f"{category.value}: {formatted_value} {currency} ({percent:.1f}%)")

            # hide negligible categories
            pie_slice.setLabelVisible(percent >= 1.0 or state.category == category)
            pie_slice.clicked.connect(
                lambda *_, c=category: _on_slice_clicked(c)
            )

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle("Category Breakdown")
        # increase font size
        font = chart.titleFont()
        font.setPointSize(13)
        chart.setTitleFont(font)
        chart.setBackgroundRoundness(0)

        # disable legend, it's messy because of the categories
        chart.legend().setVisible(False)

        # set chart finally
        self.ui.chart_widget.setChart(chart)

    def _build_line_chart(
        self,
        txs: list[Transaction],
        state: DashboardState
    ) -> None:

        # build chart axis from full transaction history, not filtered data
        full_history_months = self.tx_manager.get_history_months()

        # calculate totals for filtered transactions grouped by month
        monthly_totals = {
            month: self.tx_manager.total_amount(month_txs)
            for month, month_txs in self.tx_manager.group_by_month(txs).items()
        }

        if not monthly_totals:
            self.ui.log(
                "No data for line chart.",
                bold=True,
                color="red"
            )
            return

        # ensure all available months are shown, even without transactions
        chart_values = {
            month: monthly_totals.get(month, Decimal("0"))
            for month in full_history_months
        }

        # sort months chronologically
        chart_months = sorted(chart_values.keys())
        self._chart_months = chart_months
        self._chart_values = chart_values

        series = QLineSeries()
        series.setPointsVisible(True)
        series.clicked.connect(self._on_point_clicked)

        max_y_value = 0

        for i, month in enumerate(chart_months):
            amount = chart_values[month]
            y_value = int(amount)

            series.append(i, y_value)
            max_y_value = max(max_y_value, y_value)

        # format only for the axis labels
        month_labels = [
            datetime.strptime(m, "%Y-%m").strftime("%y/%m")
            for m in chart_months
        ]

        chart = QChart()
        chart.addSeries(series)
        chart.setTitle(state.category or "All Categories")

        # increase font size
        font = chart.titleFont()
        font.setPointSize(12)
        chart.setTitleFont(font)
        chart.setBackgroundRoundness(0)

        axis_x = QCategoryAxis()
        axis_x.setLabelsAngle(-45)
        tick_step = max(1, len(month_labels) // 15) # flood division
        for i, label in enumerate(month_labels):
            if i % tick_step == 0:
                axis_x.append(f"{label}→", i)

        axis_x.setRange(0, max(0, len(chart_months) - 1))
        chart.addAxis(axis_x, Qt.AlignmentFlag.AlignBottom)
        series.attachAxis(axis_x)

        max_y, step = self._nice_axis_max(max_y_value)
        currency = self._get_display_currency(txs)

        axis_y = QValueAxis()
        axis_y.setRange(0, max_y)
        axis_y.setTickInterval(step)
        axis_y.setLabelFormat(f"%d {currency}")

        chart.addAxis(axis_y, Qt.AlignmentFlag.AlignLeft)
        series.attachAxis(axis_y)

        chart.legend().setVisible(False)
        self.ui.chart_widget.setChart(chart)

    @staticmethod
    def _nice_axis_max(value: int) -> tuple[int, int]:
        if value <= 0:
            return 50, 10

        raw_step = value / 8  # target ~8 ticks

        magnitude = 10 ** math.floor(math.log10(raw_step))
        normalized = raw_step / magnitude

        if normalized <= 1:
            nice_step = 1
        elif normalized <= 2:
            nice_step = 2
        elif normalized <= 5:
            nice_step = 5
        else:
            nice_step = 10

        step = int(nice_step * magnitude)
        max_val = math.ceil(value / step) * step

        return max_val, step
