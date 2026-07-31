#=================================================
# IMPORT
#=================================================
import sys

from pathlib import Path

from csv_reader import read_transactions
from models import Category, ChartMode, DashboardState
from ui_manager import UIManager
from override_service import OverrideRepository, TxCategoryOverrideService
from tx_manager import TxManager

from PySide6.QtCharts import QChartView
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import (QColor, QFont, QPainter, QTextCharFormat, QTextCursor, QTextOption)
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QCheckBox, QComboBox, QDialog, QDialogButtonBox,
    QFrame, QGridLayout, QHBoxLayout, QHeaderView, QLabel, QListWidget,
    QListWidgetItem, QMainWindow, QPushButton, QSizePolicy, QSplitter,
    QTableView, QTextEdit, QVBoxLayout, QWidget
)

#=================================================
# MAIN WINDOW
#=================================================
class MainWindow(QMainWindow):
    ui_manager: UIManager

    def __init__(
        self,
        tx_manager: TxManager
    ):
        super().__init__()

        # get service instances
        self.tx_manager = tx_manager

        # chart mode attribute
        self.chart_mode: ChartMode = ChartMode.PIE

        # UI widgets
        self.panel: QWidget
        self.bank_dropdown: QComboBox
        self.partner_dropdown: QComboBox
        self.category_dropdown: QComboBox
        self.year_dropdown: QComboBox
        self.time_range_dropdown: QComboBox

        self.text_output: QTextEdit
        self.pie_chart_toggle: QPushButton
        self.line_chart_toggle: QPushButton

        # visibility
        self.major_expenses_checkbox: QCheckBox
        self.loan_repay_checkbox: QCheckBox
        self.loan_prepay_checkbox: QCheckBox
        self.salary_checkbox: QCheckBox

        # options
        self.monthly_avg_chart_checkbox: QCheckBox
        self.hide_largest_category_checkbox: QCheckBox
        self.export_table_button: QPushButton

        # table, chart
        self.table_output: QTableView
        self.chart_widget: QChartView

        self._init_window()
        self._init_filters()
        self._init_buttons()
        self._build_main_layout()

    #=================================================
    # init window
    #=================================================
    def _init_window(self) -> None:
        self.setWindowTitle("Transactions v1.0.0")
        self.resize(1800, 1000)

        self.panel = QWidget()
        self.setCentralWidget(self.panel)

    #=================================================
    # ComboBox filters (dropdowns)
    #=================================================
    def _init_filters(self) -> None:
        self.bank_dropdown = QComboBox()
        self.partner_dropdown = QComboBox()
        self.category_dropdown = QComboBox()
        self.year_dropdown = QComboBox()
        self.time_range_dropdown = QComboBox()

        # increase font size for dropdowns
        font: QFont = self.category_dropdown.font()
        font.setPointSize(font.pointSize() + 1)

        for cb in (
            self.bank_dropdown,
            self.partner_dropdown,
            self.category_dropdown,
            self.year_dropdown,
            self.time_range_dropdown
        ):
            # cb.setMinimumWidth(200)
            cb.setMinimumHeight(50)
            cb.setCurrentIndex(0)
            cb.setFont(font)            # for closed combobox text
            cb.view().setFont(font)     # for dropdown list items
            cb.setEditable(True)
            line_edit = cb.lineEdit()
            if line_edit is not None:
                line_edit.setAlignment(Qt.AlignmentFlag.AlignCenter)

    #=================================================
    # chart toggle
    #=================================================
    def _init_buttons(self) -> None:
        #===================
        # toggle buttons
        #===================
        toggle_style = (
            "QPushButton { background-color: none; }"
            "QPushButton:checked { background-color: rgb(220,220,220); }"
        )

        self.pie_chart_toggle = QPushButton("Pie")
        self.line_chart_toggle = QPushButton("Line")

        self.pie_chart_toggle.setStyleSheet(toggle_style)
        self.line_chart_toggle.setStyleSheet(toggle_style)

        font_for_button: QFont = QFont(self.pie_chart_toggle.font())
        font_for_button.setPointSize(font_for_button.pointSize() + 1)

        for btn in (self.pie_chart_toggle, self.line_chart_toggle):
            btn.setCheckable(True)
            btn.setStyleSheet(toggle_style)
            btn.setFont(font_for_button)
            # btn.setMinimumWidth(100)
            btn.setMinimumHeight(50)

        self.pie_chart_toggle.setChecked(True)
        self.line_chart_toggle.setChecked(False)

    #=================================================
    # text output
    #=================================================
    def _build_text_container(self) -> QWidget:
        #==================================
        # wrapper frame for text_output
        #==================================
        text_container = QFrame()
        text_container.setStyleSheet("""
            QFrame {
                background-color: rgb(243, 243, 243);
                border: 1px solid rgba(0, 0, 0, 80);
                border-radius: 3px;
            }
        """)

        # text wrapper is passed as a parent
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)

        self.text_output = QTextEdit()
        self.text_output.setReadOnly(True)

        # horizontal ignored, vertical allowed
        self.text_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.text_output.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.text_output.document().setDocumentMargin(10)
        self.text_output.setFrameStyle(QFrame.Shape.NoFrame)

        self.text_output.setStyleSheet("""
            QTextEdit, QTextEdit:focus {
                background-color: rgb(243, 243, 243);
                border: 1px solid rgba(0, 0, 0, 40);
            }
        """)

        font = self.text_output.font()
        font.setFamily("Source Code Pro")
        font.setPointSize(font.pointSize() + 1)
        self.text_output.setFont(font)

        # add QTextEdit into the layout
        text_layout.addWidget(self.text_output)

        # go with a widget, so it can be treated as a single thing later
        # e.g.: hiding a widget removes it from the layout (layouts alone can’t do that)
        return text_container

    #=================================================
    # control + text + chart
    #=================================================
    def _build_chart_toggle(self) -> QWidget:
        toggle_layout = QHBoxLayout()
        toggle_layout.setContentsMargins(0, 0, 0, 0)
        # toggle_layout.setSpacing(5)

        toggle_layout.addWidget(self.pie_chart_toggle)
        toggle_layout.addWidget(self.line_chart_toggle)

        container = QWidget()
        container.setLayout(toggle_layout)
        return container

    def _build_control_panel(self) -> QWidget:
        control_layout = QGridLayout()
        control_layout.setContentsMargins(10, 10, 10, 0)

        control_layout.addWidget(self.bank_dropdown, 0, 0)          # r=0, c=0
        control_layout.addWidget(self.partner_dropdown, 0, 1)       # r=0, c=1
        control_layout.addWidget(self.category_dropdown, 0, 2)      # r=0, c=2
        control_layout.addWidget(self.year_dropdown, 1, 0)          # r=1, c=0
        control_layout.addWidget(self.time_range_dropdown, 1, 1)    # r=1, c=1
        control_layout.addWidget(self._build_chart_toggle(), 1, 2)  # r=1, c=2

        control_layout.setColumnStretch(0, 1)
        control_layout.setColumnStretch(1, 1)
        control_layout.setColumnStretch(2, 1)

        # rowSpan=2 so the text output occupies both rows
        control_layout.addWidget(self._build_text_container(), 0, 3, 2, 1)
        control_layout.setColumnStretch(3, 3)

        container = QWidget()
        container.setLayout(control_layout)

        # allow widget to expand horizontally within the layout
        container.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        return container

    def _build_chart_container(self) -> QWidget:
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)

        layout.addWidget(self._build_control_panel())

        self.chart_widget = QChartView()
        self.chart_widget.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.chart_widget)

        options = QHBoxLayout()

        self.major_expenses_checkbox = QCheckBox("Major expenses")

        # repayments are enabled by default
        self.loan_repay_checkbox = QCheckBox("Loan repayments")
        self.loan_repay_checkbox.setChecked(True)
        self.loan_prepay_checkbox = QCheckBox("Loan prepayments")
        self.salary_checkbox = QCheckBox("Salary")

        self.monthly_avg_chart_checkbox = QCheckBox("Monthly averages")
        self.hide_largest_category_checkbox = QCheckBox("Hide largest category")
        self.export_table_button = QPushButton("Export table")

        include_layout = QHBoxLayout()
        include_layout.addWidget(QLabel("SHOW"))
        include_layout.addSpacing(10)
        include_layout.addWidget(self.major_expenses_checkbox)
        include_layout.addWidget(self.loan_repay_checkbox)
        include_layout.addWidget(self.loan_prepay_checkbox)
        include_layout.addWidget(self.salary_checkbox)

        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("OPTIONS"))
        options_layout.addSpacing(10)
        # options_layout.addWidget(self.pie_hide_largest_checkbox)
        options_layout.addWidget(self.monthly_avg_chart_checkbox)
        options_layout.addWidget(self.export_table_button)

        options.addStretch()
        options.addLayout(include_layout)
        options.addSpacing(50)
        options.addLayout(options_layout)
        options.addStretch()

        layout.addLayout(options)

        container = QWidget()
        container.setLayout(layout)
        return container

    #=================================================
    # table_container
    #=================================================
    def _build_table_container(self) -> QWidget:
        table_layout = QVBoxLayout()
        table_layout.setContentsMargins(0, 0, 0, 0)

        # column output, set colors
        self.table_output = QTableView()
        self.table_output.setStyleSheet("""
            QTableView {
                background-color: rgb(240, 240, 240);
                gridline-color: gray;
            }
            QTableView::item:selected {
                background-color: rgb(210, 225, 200);
                color: rgb(30, 28, 24);
            }
            QHeaderView::section {
                background-color: rgb(220, 220, 220);
                padding: 4px;
                border: 1px solid gray;
            }
        """)

        self.table_output.setSortingEnabled(False)
        self.table_output.verticalHeader().setVisible(False)
        self.table_output.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.table_output.setSelectionBehavior(QTableView.SelectionBehavior.SelectItems)
        self.table_output.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table_output.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table_output.horizontalHeader().setStretchLastSection(False)

        table_layout.addWidget(self.table_output)
        table_container = QWidget()
        table_container.setLayout(table_layout)
        return table_container

    #=================================================
    # main_layout
    #=================================================
    def _build_main_layout(self) -> None:
        main_layout = QVBoxLayout()

        # table | chart in a splitter
        chart_table_splitter = QSplitter(Qt.Orientation.Horizontal)
        chart_table_splitter.addWidget(self._build_table_container())
        chart_table_splitter.addWidget(self._build_chart_container())
        chart_table_splitter.setStretchFactor(0, 51)
        chart_table_splitter.setStretchFactor(1, 20)

        main_layout.addWidget(chart_table_splitter)
        self.panel.setLayout(main_layout)

    #==================================
    # UI helpers
    #==================================
    def log(
        self,
        message: str,
        bold: bool = False,
        color: str | None = None
    ):
        cursor = self.text_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        fmt = QTextCharFormat()
        if bold:
            fmt.setFontWeight(QFont.Weight.Bold)
        if color:
            fmt.setForeground(QColor(color))

        cursor.insertText(f"{message}\n", fmt)
        # self.text_output.setTextCursor(cursor)
        # self.text_output.setFocus()

    #==================================
    # UI API (for UIManager)
    #==================================
    def get_dashboard_state(self) -> DashboardState:
        return DashboardState(
            bank=self.bank_dropdown.currentData(),
            partner=self.partner_dropdown.currentData(),
            category=self.category_dropdown.currentData(),
            year=self.year_dropdown.currentData(),
            time_range=self.time_range_dropdown.currentData(),

            include_major_expenses=self.major_expenses_checkbox.isChecked(),
            include_loan_repay=self.loan_repay_checkbox.isChecked(),
            include_loan_prepay=self.loan_prepay_checkbox.isChecked(),
            include_salary=self.salary_checkbox.isChecked(),

            monthly_average=self.monthly_avg_chart_checkbox.isChecked(),
            hide_largest_category=self.hide_largest_category_checkbox.isChecked(),
        )

    def set_selected_category(self, category: Category | None) -> None:
        cb = self.category_dropdown
        with QSignalBlocker(cb):
            if category is None:
                cb.setCurrentIndex(0)
                return

            for i in range(cb.count()):
                if cb.itemData(i) == category:
                    cb.setCurrentIndex(i)
                    return

    def set_chart_mode(self, mode: ChartMode) -> None:
        self.chart_mode = mode

    def get_chart_mode(self) -> ChartMode:
        return self.chart_mode

    #==================================
    # load / IO
    #==================================
    @staticmethod
    def select_csv_files(parent=None, directory: Path = Path(".")) -> list[Path]:
        csv_files = sorted(directory.glob("*.csv"))

        dialog = QDialog(parent)
        dialog.setWindowTitle("Select CSV Files")
        dialog.resize(400, 300)

        layout = QVBoxLayout(dialog)

        list_widget = QListWidget()
        list_widget.setSelectionMode(
            QAbstractItemView.SelectionMode.MultiSelection
        )

        for csv in csv_files:
            item = QListWidgetItem(csv.name)
            item.setData(0x0100, csv)  # Qt.UserRole
            list_widget.addItem(item)

        layout.addWidget(list_widget)

        buttons = QDialogButtonBox()
        buttons.addButton(QDialogButtonBox.StandardButton.Ok)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return []

        return [
            item.data(0x0100)
            for item in list_widget.selectedItems()
        ]

    def add_transactions_from_csv(self, file_path: Path):

        try:
            new_transactions, format_name = read_transactions(file_path)
        except ValueError as e:
            self.log(str(e), bold=True, color="red")
            return

        if not new_transactions:
            self.log(
                f"No transactions in file: {file_path.name}.",
                bold=True,
                color="orange"
            )
            return

        # add loaded transactios to manager, categorization happens there
        overridden_txs = self.tx_manager.process_transactions(new_transactions)

        self.log(
            f"Loaded {len(new_transactions)} transactions / "
            f"format: {format_name} / "
            f"category overrides: {overridden_txs}",
        )
        
    def log_transaction_warnings(self) -> None:
        
        # warn about incomplete latest month
        if self.tx_manager.last_month_is_incomplete:
            self.log(
                "Note: The latest month appears to be incomplete.\n"
                "Monthly averages may be lower than expected.",
                bold=True,
                color="orange",
            )
        
        # warn about missing override matches
        if not self.tx_manager.category_overrides.all_found():
            self.log(
                f"Overrides without matching transactions:",
                bold=True,
                color="orange"
            )
                
            for tx_id in self.tx_manager.category_overrides.missing_overrides():
                self.log(
                    f"  • {tx_id}",
                    color="orange"
                )

    def init_ui(self) -> None:
        if not self.tx_manager.has_transactions:
            self.log(
                "No transactions were loaded.",
                bold=True,
                color="red"
            )
            return

        self.ui_manager.update_bank_dropdown()
        self.ui_manager.update_partner_dropdown()
        self.ui_manager.update_category_dropdown()
        self.ui_manager.update_year_dropdown()
        self.ui_manager.update_time_range_dropdown()

        # initial state is unfiltered state
        self.ui_manager.refresh_ui()

#=================================================
# ENTRY POINT
#=================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)

    script_dir = Path(__file__).parent

    # prepare services
    repo = OverrideRepository(str(script_dir / "overrides.json"))
    override_service = TxCategoryOverrideService(repo)

    # prepare the manager
    transaction_manager = TxManager(override_service)

    # main window and manager
    window = MainWindow(transaction_manager)
    window.ui_manager = UIManager(window, transaction_manager)

    # popup window for files selection
    selected_files = window.select_csv_files(window, script_dir)

    for csv_file in selected_files:
        window.add_transactions_from_csv(csv_file)

    window.log_transaction_warnings()

    window.init_ui()
    window.show()

    sys.exit(app.exec())
