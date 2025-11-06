import sys
import csv
import re
from datetime import datetime
from typing import List, Tuple, Optional

import Main_database as dbmod

from PyQt6.QtWidgets import (
    QApplication,QWidget,QLabel,QLineEdit,QPushButton,QVBoxLayout,QHBoxLayout,QListWidget,QStackedWidget,QGridLayout,QMessageBox,QFileDialog,
    QScrollArea,QCheckBox,QFormLayout,QSpinBox,QTableWidget,QTableWidgetItem,QHeaderView,QDateEdit,QInputDialog,
)
from PyQt6.QtCore import Qt, QDate

# ---------- CONFIG ----------
DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = #ENTER PASSWORD HERE
DB_NAME = "attendance"
ADMIN_PASSWORD = "123"

# instantiate DB wrapper
db = dbmod.AttendanceDB(
    host=DB_HOST,
    user=DB_USER,
    password=DB_PASSWORD,
    database=DB_NAME,
    admin_password=ADMIN_PASSWORD,
)

# ---------- Small utilities ----------
def show_error(title: str, msg: str):
    QMessageBox.critical(None, title, msg)

def show_info(title: str, msg: str):
    QMessageBox.information(None, title, msg)

def is_valid_identifier(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_]*$", name))

# ---------- Transient state manager ----------
class AppState:
    """Holds last_logged_in_class and last_student_list (Roll_no,name)"""
    last_logged_in_class: Optional[str] = None
    last_student_list: List[Tuple[int, str]] = []
    last_absent_list: List[int] = []
    last_class_password: Optional[str] = None

    # Admin flag
    is_admin: bool = False

    @classmethod
    def set_class_password(cls, pw: Optional[str]):
        cls.last_class_password = pw

    @classmethod
    def get_class_password(cls) -> Optional[str]:
        return cls.last_class_password

    @classmethod
    def set_logged_class(cls, name: Optional[str]):
        cls.last_logged_in_class = name

    @classmethod
    def get_logged_class(cls) -> Optional[str]:
        return cls.last_logged_in_class

    @classmethod
    def set_students(cls, students: List[Tuple[int, str]]):
        cls.last_student_list = students

    @classmethod
    def get_students(cls) -> List[Tuple[int, str]]:
        return cls.last_student_list

    @classmethod
    def set_absent(cls, absent: List[int]):
        cls.last_absent_list = absent

    @classmethod
    def get_absent(cls) -> List[int]:
        return cls.last_absent_list

    # Admin flag methods
    @classmethod
    def set_is_admin(cls, value: bool):
        cls.is_admin = bool(value)

    @classmethod
    def is_admin_user(cls) -> bool:
        return bool(cls.is_admin)

# ---------- GLOBAL STYLE ----------
GLOBAL_STYLE = """
    QWidget {
        background-color: #f3f6fa;
        color: #222;
        font-family: 'Segoe UI';
        font-size: 13px;
    }

    /* Buttons */
    QPushButton {
        background-color: #0078d4;
        color: white;
        border: none;
        padding: 7px 14px;
        border-radius: 6px;
        font-weight: 500;
    }
    QPushButton:hover { background-color: #3399ff; }
    QPushButton:pressed { background-color: #005ea0; }

    /* Inputs */
    QLineEdit, QSpinBox, QDateEdit {
        background-color: #ffffff;
        border: 1px solid #c7ced6;
        border-radius: 5px;
        padding: 6px 8px;
        min-height: 28px;
    }
    QLineEdit:focus, QSpinBox:focus, QDateEdit:focus {
        border: 1px solid #0078d4;
        outline: none;
    }
    QDateEdit { min-width: 150px; }

    QLabel[role="title"] {
        font-size: 22px;
        font-weight: bold;
        color: #1a1a1a;
        margin-bottom: 12px;
    }
    QLabel[role="subtitle"] {
        font-size: 12px;
        color: #666;
    }

    QListWidget, QScrollArea, QTableWidget {
        border: 1px solid #d2d9e1;
        border-radius: 6px;
        background-color: #ffffff;
    }

    QTableWidget {
        gridline-color: #d0d7df;
        selection-background-color: #dcecff;
        alternate-background-color: #f7f9fc;
    }
    QHeaderView::section {
        background-color: #eef3f8;
        padding: 5px;
        border: none;
        font-weight: bold;
    }

    QCheckBox {
        spacing: 6px;
        color: black;
        font-size: 13px;
    }
    QCheckBox::indicator {
        width: 16px;
        height: 16px;
        border-radius: 3px;
        border: 1px solid #0078d4;
        background-color: white;
    }
    QCheckBox::indicator:hover {
        border: 1px solid #3399ff;
    }
    QCheckBox::indicator:checked {
        background-color: #0078d4;
        image: url(:/qt-project.org/styles/commonstyle/images/checkboxindicator.png);
    }
"""

# ---------- Login Widget (admin-aware) ----------
class LoginWidget(QWidget):

    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(200, 120, 200, 120)
        v.setSpacing(25)

        # Title
        title = QLabel("Attendance Manager")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        # Form layout
        form = QFormLayout()
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        self.class_input.setPlaceholderText("Class name (e.g., class12A)")

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_input.setPlaceholderText("Password")

        form.addRow("Class:", self.class_input)
        form.addRow("Password:", self.password_input)
        v.addLayout(form)

        # Buttons row
        h = QHBoxLayout()
        h.setSpacing(12)

        btn_login = QPushButton("Login")
        btn_login.clicked.connect(self.on_login)

        btn_create = QPushButton("Create Class")
        btn_create.clicked.connect(self.on_create_class)

        btn_quit = QPushButton("Quit")
        btn_quit.clicked.connect(QApplication.instance().quit)

        h.addWidget(btn_login)
        h.addWidget(btn_create)
        h.addWidget(btn_quit)
        v.addLayout(h)

        # Subtitle note
        note = QLabel("Use the class or admin password to log in.")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setProperty("role", "subtitle")
        v.addWidget(note)

        self.setLayout(v)

    def on_login(self):
        class_name = self.class_input.text().strip()
        password = self.password_input.text().strip()

        if not class_name or not password:
            show_error("Missing fields", "Please enter class and password.")
            return
        if not is_valid_identifier(class_name):
            show_error(
                "Invalid class name",
                "Class name must start with a letter and contain only letters, digits, underscores.",
            )
            return

        try:
            # Admin sign-in detection
            if password == ADMIN_PASSWORD:
                AppState.set_is_admin(True)
                AppState.set_logged_class(class_name)
                AppState.set_class_password(password)
                try:
                    students = db.authenticate_user(class_name, password)
                    AppState.set_students(students)
                except Exception:
                    AppState.set_students([])
                show_info("Admin login", "Logged in with administrative access.")
            else:
                # Normal class login
                students = db.authenticate_user(class_name, password)
                AppState.set_is_admin(False)
                AppState.set_logged_class(class_name)
                AppState.set_class_password(password)
                AppState.set_students(students)

            self.nav.goto_dashboard()

        except Exception as e:
            show_error("Login failed", str(e))

    def on_create_class(self):

        class_name, ok = QInputDialog.getText(self, "Create Class", "Enter new class name:")
        if not ok or not class_name.strip():
            return
        class_name = class_name.strip()

        if not is_valid_identifier(class_name):
            show_error(
                "Invalid Name",
                "Class name must start with a letter and contain only letters, digits, underscores.",
            )
            return

        try:

            db.create_table_for_class(class_name)

            pw, ok2 = QInputDialog.getText(
                self,
                "Set Class Password",
                f"Enter password for '{class_name}':",
                QLineEdit.EchoMode.Password,
            )

            if ok2 and pw.strip():
                db.set_class_password(class_name, pw.strip())
                show_info("Created", f"Class '{class_name}' created with its own password.")
            else:
                show_info("Created", f"Class '{class_name}' created, but no password set yet.")

            self.class_input.setText(class_name)

        except Exception as e:
            show_error("Create failed", str(e))

# ---------- Main Window ----------
class Navigator(QWidget):
    """Manages screens and top-level app layout and styling."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Attendance Manager")
        self.setMinimumSize(900, 700)
        self._build_ui()
        try:
            db.connect()
        except Exception as e:
            show_error("DB Connect", f"Could not connect at startup: {e}")

    def _build_ui(self):
        main_v = QVBoxLayout()
        # toolbar
        toolbar = QHBoxLayout()
        label = QLabel("Attendance Manager")
        label.setStyleSheet("font-size:18px; font-weight:bold;")
        toolbar.addWidget(label)
        toolbar.addStretch()
        self.lbl_status = QLabel("Ready")
        toolbar.addWidget(self.lbl_status)
        main_v.addLayout(toolbar)

        # stacked pages
        self.stack = QStackedWidget()
        # instantiate pages
        self.login = LoginWidget(self)
        self.dashboard = None
        self.display = None
        self.select_absent = None
        self.add_student = None
        self.import_csv = None
        self.delete_page = None
        self.history = None

        # Create pages
        self.dashboard = DashboardWidget(self)
        self.display = DisplayWidget(self)
        self.select_absent = SelectAbsentWidget(self)
        self.add_student = AddStudentWidget(self)
        self.import_csv = ImportCSVWidget(self)
        self.delete_page = DeleteWidget(self)
        self.history = HistoryWidget(self)

        self.stack.addWidget(self.login)         # index 0
        self.stack.addWidget(self.dashboard)     # index 1
        self.stack.addWidget(self.display)       # index 2
        self.stack.addWidget(self.select_absent) # index 3
        self.stack.addWidget(self.add_student)   # index 4
        self.stack.addWidget(self.import_csv)    # index 5
        self.stack.addWidget(self.delete_page)   # index 6
        self.stack.addWidget(self.history)       # index 7

        main_v.addWidget(self.stack)
        self.setLayout(main_v)

        # default to login
        self.goto_login()

        # apply global style
        self.setStyleSheet(GLOBAL_STYLE)

    def goto_login(self):
        self.stack.setCurrentWidget(self.login)
        self.lbl_status.setText("Login")

    def _apply_class_field_state(self, widget_with_class_input, prefill: Optional[str] = None):

        if not widget_with_class_input:
            return
        if prefill:
            try:
                widget_with_class_input.class_input.setText(prefill)
            except Exception:
                pass

        if AppState.is_admin_user():
            widget_with_class_input.class_input.setReadOnly(False)
            widget_with_class_input.class_input.setStyleSheet("")  # clear grey
        else:
            widget_with_class_input.class_input.setReadOnly(True)
            widget_with_class_input.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def goto_dashboard(self):
        # refresh dashboard with last state
        self.dashboard.refresh()
        self.stack.setCurrentWidget(self.dashboard)
        self.lbl_status.setText(f"Dashboard — {AppState.get_logged_class() or 'not logged'}")

    def goto_display(self):
        # prefill class & date
        pre = AppState.get_logged_class() or ""
        self._apply_class_field_state(self.display, prefill=pre)

        if hasattr(self.display, "apply_admin_state"):
            self.display.apply_admin_state()

        self.stack.setCurrentWidget(self.display)
        self.lbl_status.setText("Students")


    def goto_select(self):
        pre = AppState.get_logged_class() or ""
        self._apply_class_field_state(self.select_absent, prefill=pre)
        self.stack.setCurrentWidget(self.select_absent)
        self.lbl_status.setText("Select Absent")

    def goto_add(self):
        pre = AppState.get_logged_class() or ""
        self._apply_class_field_state(self.add_student, prefill=pre)
        self.stack.setCurrentWidget(self.add_student)
        self.lbl_status.setText("Add Student")

    def goto_import(self):
        pre = AppState.get_logged_class() or ""
        self._apply_class_field_state(self.import_csv, prefill=pre)
        self.stack.setCurrentWidget(self.import_csv)
        self.lbl_status.setText("Import CSV")

    def goto_delete(self):
        pre = AppState.get_logged_class() or ""
        self._apply_class_field_state(self.delete_page, prefill=pre)
        self.stack.setCurrentWidget(self.delete_page)
        self.lbl_status.setText("Delete")

    def goto_history(self):
        pre = AppState.get_logged_class() or ""
        self._apply_class_field_state(self.history, prefill=pre)
        self.stack.setCurrentWidget(self.history)
        self.lbl_status.setText("History")

# ---------- Widgets ----------
class DashboardWidget(QWidget):
    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self._build_ui()

    def _build_ui(self):
        # Main layout
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(25)

        # Title
        title = QLabel("Dashboard")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel("Class:"))
        self.class_label = QLabel("(none)")
        self.class_label.setStyleSheet("font-weight:600;color:#333;")
        header.addWidget(self.class_label)
        header.addStretch()

        header.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit(QDate.currentDate())
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setEnabled(False)
        self.date_edit.setButtonSymbols(QDateEdit.ButtonSymbols.NoButtons)
        self.date_edit.setFixedWidth(
            self.date_edit.fontMetrics().horizontalAdvance(self.date_edit.text()) + 24
        )
        self.date_edit.setStyleSheet("""
            QDateEdit {
                background-color: white;
                color: black;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding: 0px 3px;
                min-width: 30px;
            }
        """)
        header.setSpacing(7)
        header.addWidget(self.date_edit)
        v.addLayout(header)

        grid = QGridLayout()
        grid.setSpacing(15)

        buttons = [
            ("View Students", lambda: self.nav.goto_display()),
            ("Select Absent", lambda: self.nav.goto_select()),
            ("Mark All Present", self.on_mark_all_present),
            ("Add Student", lambda: self.nav.goto_add()),
            ("Import CSV", lambda: self.nav.goto_import()),
            ("Delete Students", lambda: self.nav.goto_delete()),
            ("Attendance History", lambda: self.nav.goto_history()),
        ]

        for i, (text, fn) in enumerate(buttons[:6]):
            b = QPushButton(text)
            b.setMinimumHeight(36)
            b.clicked.connect(fn)
            grid.addWidget(b, i // 3, i % 3)

        v.addLayout(grid)

        center_container = QWidget()
        center_layout = QHBoxLayout(center_container)
        center_layout.addStretch()
        hist_btn = QPushButton("Attendance History")
        hist_btn.setMinimumHeight(36)
        hist_btn.clicked.connect(buttons[6][1])
        center_layout.addWidget(hist_btn)
        center_layout.addStretch()
        center_layout.setContentsMargins(0, 0, 0, 0)
        v.addWidget(center_container)

        logout_container = QWidget()
        logout_layout = QHBoxLayout(logout_container)
        logout_layout.addStretch()
        btn_logout = QPushButton("Logout")
        btn_logout.setMinimumHeight(36)
        btn_logout.setStyleSheet("""
            QPushButton {
                background-color: #d9534f;
                color: white;
                font-weight: 600;
                border-radius: 6px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #c9302c;
            }
        """)
        btn_logout.clicked.connect(self.on_logout)
        logout_layout.addWidget(btn_logout)
        logout_layout.addStretch()
        logout_layout.setContentsMargins(0, 10, 0, 0)
        v.addWidget(logout_container)

        self.preview_label = QLabel("Preview (first 50 students):")
        self.preview_label.setProperty("role", "subtitle")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.preview_label.setStyleSheet("font-weight:600; color:#444; margin-top:12px;")
        v.addWidget(self.preview_label)

        preview_container = QWidget()
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(10, 8, 10, 8)

        self.preview_list = QListWidget()
        self.preview_list.setMaximumHeight(200)
        self.preview_list.setStyleSheet("""
            QListWidget {
                background: #f9f9f9;
                border: 1px solid #ccc;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
                color: #333;
            }
            QListWidget::item {
                padding: 4px 8px;
                border-bottom: 1px solid #e6e6e6;
            }
            QListWidget::item:selected {
                background-color: #d0e7ff;
                color: #000;
                border-radius: 4px;
            }
        """)
        preview_layout.addWidget(self.preview_list)
        v.addWidget(preview_container)

        self.setLayout(v)

    def refresh(self):
        class_name = AppState.get_logged_class()
        self.class_label.setText(class_name if class_name else "(none)")

        students = AppState.get_students()
        self.preview_list.clear()
        for roll, name in students[:50]:
            self.preview_list.addItem(f"{roll} — {name}")

    def on_mark_all_present(self):
        class_name = AppState.get_logged_class()
        if not class_name:
            show_error("Not logged in", "Please login first.")
            self.nav.goto_login()
            return

        date_qdate = self.date_edit.date()
        dt = datetime(date_qdate.year(), date_qdate.month(), date_qdate.day())

        try:
            db.mark_all_present(class_name, dt)
            show_info("Success", f"All students marked Present on {dt.strftime('%Y-%m-%d')}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            AppState.set_absent([])
        except Exception as e:
            show_error("Failed", str(e))

    def on_logout(self):
        # Clear admin flag on logout
        AppState.set_is_admin(False)
        AppState.set_logged_class(None)
        AppState.set_students([])
        AppState.set_absent([])
        # go back to login screen
        self.nav.goto_login()

# ---------- DisplayWidget ----------
class DisplayWidget(QWidget):

    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self.table: Optional[QTableWidget] = None
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(20)

        title = QLabel("Students & Attendance (editable)")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        row = QHBoxLayout()
        row.addWidget(QLabel("Class:"))
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        row.addWidget(self.class_input)

        if not AppState.is_admin_user():
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")
        else:
            self.class_input.setReadOnly(False)

        row.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        row.addWidget(self.date_edit)
        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self.load_table_for_date)
        row.addWidget(btn_load)
        btn_save = QPushButton("Save Changes")
        btn_save.clicked.connect(self.save_changes)
        row.addWidget(btn_save)
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self.export_csv)
        row.addWidget(btn_export)
        v.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Roll No", "Student Name", "Attendance"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.table)

        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.nav.goto_dashboard())
        v.addWidget(btn_back)

        self.setLayout(v)

    def apply_admin_state(self):
        """Called by Navigator before showing this page to ensure class_input state matches admin flag."""
        if AppState.is_admin_user():
            self.class_input.setReadOnly(False)
            self.class_input.setStyleSheet("")
        else:
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def load_table_for_date(self):
        class_name = self.class_input.text().strip()
        if not class_name:
            show_error("Missing", "Provide class name.")
            return
        if not is_valid_identifier(class_name):
            show_error("Invalid", "Class name must be valid identifier.")
            return

        date_qdate = self.date_edit.date()
        dt = datetime(date_qdate.year(), date_qdate.month(), date_qdate.day())
        colname = dt.strftime("%Y_%m_%d")

        try:
            db.connect()
            if not db._column_exists(class_name, colname):
                db.cursor.execute(
                    f"ALTER TABLE `{class_name}` ADD COLUMN `{colname}` VARCHAR(20) DEFAULT 'Absent';"
                )
                db.conn.commit()

            q = f"SELECT Roll_no, Student_name, `{colname}` FROM `{class_name}` ORDER BY Roll_no;"
            db.cursor.execute(q)
            rows = db.cursor.fetchall()

            self.table.setRowCount(len(rows))
            for r, row in enumerate(rows):
                roll_item = QTableWidgetItem(str(row[0]))
                roll_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)

                name_item = QTableWidgetItem(row[1] if row[1] is not None else "")
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable
                    | Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsEditable
                )

                att_text = row[2] if row[2] is not None else "Absent"
                chk = QCheckBox()
                chk.setChecked(att_text.lower() == "present")

                container = QWidget()
                layout = QHBoxLayout(container)
                layout.addStretch()
                layout.addWidget(chk)
                layout.addStretch()
                layout.setContentsMargins(0, 0, 0, 0)
                self.table.setItem(r, 0, roll_item)
                self.table.setItem(r, 1, name_item)
                self.table.setCellWidget(r, 2, container)

            AppState.set_logged_class(class_name)
            AppState.set_students([(row[0], row[1]) for row in rows])

        except Exception as e:
            show_error("Load failed", str(e))

    def save_changes(self):
        class_name = self.class_input.text().strip()
        if not class_name:
            show_error("Missing", "Provide class name.")
            return

        date_qdate = self.date_edit.date()
        dt = datetime(date_qdate.year(), date_qdate.month(), date_qdate.day())
        colname = dt.strftime("%Y_%m_%d")

        if self.table.rowCount() == 0:
            show_info("No data", "Nothing to save.")
            return

        try:
            db.connect()
            if not db._column_exists(class_name, colname):
                db.cursor.execute(
                    f"ALTER TABLE `{class_name}` ADD COLUMN `{colname}` VARCHAR(20) DEFAULT 'Absent';"
                )
                db.conn.commit()

            for r in range(self.table.rowCount()):
                roll = int(self.table.item(r, 0).text())
                name_item = self.table.item(r, 1)
                name_val = name_item.text().strip() if name_item else ""

                container = self.table.cellWidget(r, 2)
                chk = container.findChild(QCheckBox) if container else None
                att_val = "Present" if (chk and chk.isChecked()) else "Absent"

                if name_val:
                    db.cursor.execute(
                        f"UPDATE `{class_name}` SET Student_name=%s WHERE Roll_no=%s;",
                        (name_val, roll),
                    )

                db.cursor.execute(
                    f"UPDATE `{class_name}` SET `{colname}`=%s WHERE Roll_no=%s;",
                    (att_val, roll),
                )

            db.conn.commit()
            show_info("Saved", "Changes saved to database.")

        except Exception as e:
            show_error("Save failed", str(e))

    def export_csv(self):
        if self.table.rowCount() == 0:
            show_info("No data", "No table data to export.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Save attendance CSV", "", "CSV Files (*.csv)"
        )
        if not path:
            return

        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Roll_no", "Student_name", "Attendance"])
                for r in range(self.table.rowCount()):
                    roll = self.table.item(r, 0).text()
                    name = self.table.item(r, 1).text()

                    container = self.table.cellWidget(r, 2)
                    chk = container.findChild(QCheckBox) if container else None
                    att = "Present" if (chk and chk.isChecked()) else "Absent"

                    writer.writerow([roll, name, att])
            show_info("Exported", f"Exported to {path}")
        except Exception as e:
            show_error("Export failed", str(e))

# ---------- SelectAbsentWidget ----------
class SelectAbsentWidget(QWidget):

    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self.checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(16)

        title = QLabel("Select Absentees")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        # class & date
        row = QHBoxLayout()
        row.addWidget(QLabel("Class:"))
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        row.addWidget(self.class_input)

        if not AppState.is_admin_user():
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

        row.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        row.addWidget(self.date_edit)
        btn_load = QPushButton("Load Students")
        btn_load.clicked.connect(self.load_students)
        row.addWidget(btn_load)
        v.addLayout(row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        v.addWidget(self.scroll)

        # actions
        btn_row = QHBoxLayout()
        btn_mark = QPushButton("Mark Selected Absent")
        btn_mark.clicked.connect(self.mark_selected_absent)
        btn_clear = QPushButton("Clear Selection")
        btn_clear.clicked.connect(self.clear_selection)
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.nav.goto_dashboard())
        btn_row.addWidget(btn_back)
        btn_row.addWidget(btn_clear)
        btn_row.addWidget(btn_mark)
        v.addLayout(btn_row)

        self.setLayout(v)

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.class_input.setReadOnly(False)
            self.class_input.setStyleSheet("")
        else:
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def load_students(self):
        class_name = self.class_input.text().strip()
        if not class_name:
            show_error("Missing", "Enter class name.")
            return
        if not is_valid_identifier(class_name):
            show_error("Invalid", "Class name invalid.")
            return
        try:
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)

            container = QWidget()
            cv = QVBoxLayout()
            self.checkboxes.clear()
            for roll, name in students:
                cb = QCheckBox(f"{roll} — {name}")
                self.checkboxes[roll] = cb
                cv.addWidget(cb)
            container.setLayout(cv)
            self.scroll.setWidget(container)
            AppState.set_logged_class(class_name)
        except Exception as e:
            show_error("Load failed", str(e))

    def clear_selection(self):
        for cb in self.checkboxes.values():
            cb.setChecked(False)

    def mark_selected_absent(self):
        selected = [r for r, cb in self.checkboxes.items() if cb.isChecked()]
        if not selected:
            show_info("No selection", "No students selected.")
            return
        class_name = self.class_input.text().strip()
        date_qdate = self.date_edit.date()
        dt = datetime(date_qdate.year(), date_qdate.month(), date_qdate.day())
        try:
            if not db._column_exists(class_name, dt.strftime("%Y_%m_%d")):
                db.cursor.execute(f"ALTER TABLE `{class_name}` ADD COLUMN `{dt.strftime('%Y_%m_%d')}` VARCHAR(20) DEFAULT 'Absent';")
                db.conn.commit()
            db.custom_marking_absent(class_name, selected, dt)
            AppState.set_absent(selected)
            show_info("Marked", f"Marked {len(selected)} students absent for {dt.strftime('%Y-%m-%d')}.")
            # refresh saved students
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
        except Exception as e:
            show_error("Mark failed", str(e))

# ---------- AddStudentWidget ----------
class AddStudentWidget(QWidget):
    """Add a single student to class."""
    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(12)

        title = QLabel("Add Student")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        form = QFormLayout()
        self.name_input = QLineEdit()
        self.roll_input = QSpinBox()
        self.roll_input.setMinimum(1)
        self.roll_input.setMaximum(999999)
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        form.addRow("Student name:", self.name_input)
        form.addRow("Roll no:", self.roll_input)
        form.addRow("Class:", self.class_input)
        v.addLayout(form)

        h = QHBoxLayout()
        btn_add = QPushButton("Add")
        btn_add.clicked.connect(self.on_add)
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.nav.goto_dashboard())
        h.addWidget(btn_back)
        h.addWidget(btn_add)
        v.addLayout(h)
        self.setLayout(v)

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.class_input.setReadOnly(False)
            self.class_input.setStyleSheet("")
        else:
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def on_add(self):
        name = self.name_input.text().strip()
        roll = self.roll_input.value()
        class_name = self.class_input.text().strip()
        if not name or not class_name:
            show_error("Missing", "Provide student name and class.")
            return
        try:
            db.add_individual(class_name, name, roll)
            show_info("Added", f"{name} added to {class_name}.")
            # refresh
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            AppState.set_logged_class(class_name)
            self.nav.goto_dashboard()
        except Exception as e:
            show_error("Add failed", str(e))

# ---------- ImportCSVWidget ----------
class ImportCSVWidget(QWidget):
    """Import CSV file of format (Student_name, Roll_no) into a class."""
    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(12)

        title = QLabel("Import CSV")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        row = QHBoxLayout()
        self.file_input = QLineEdit()
        self.file_input.setPlaceholderText("path/to/file.csv")
        btn_browse = QPushButton("Browse")
        btn_browse.clicked.connect(self.browse)
        row.addWidget(self.file_input)
        row.addWidget(btn_browse)
        v.addLayout(row)

        form = QFormLayout()
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        form.addRow("Class:", self.class_input)
        v.addLayout(form)

        h = QHBoxLayout()
        btn_import = QPushButton("Import")
        btn_import.clicked.connect(self.on_import)
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.nav.goto_dashboard())
        h.addWidget(btn_back)
        h.addWidget(btn_import)
        v.addLayout(h)
        self.setLayout(v)

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.class_input.setReadOnly(False)
            self.class_input.setStyleSheet("")
        else:
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select CSV", "", "CSV Files (*.csv)")
        if path:
            self.file_input.setText(path)

    def on_import(self):
        path = self.file_input.text().strip()
        class_name = self.class_input.text().strip()
        if not path or not class_name:
            show_error("Missing", "Provide file path and class name.")
            return
        try:
            db.add_data_from_csv(path, class_name)
            show_info("Imported", f"CSV imported into {class_name}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            AppState.set_logged_class(class_name)
            self.nav.goto_dashboard()
        except Exception as e:
            show_error("Import failed", str(e))

# ---------- DeleteWidget ----------
class DeleteWidget(QWidget):
    """Select and delete students from the DB."""
    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self.checkboxes = {}
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(12)

        title = QLabel("Delete Students")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        form = QHBoxLayout()
        form.addWidget(QLabel("Class:"))
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self.load_students)
        form.addWidget(self.class_input)
        form.addWidget(btn_load)
        v.addLayout(form)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        v.addWidget(self.scroll)

        h = QHBoxLayout()
        btn_delete = QPushButton("Delete Selected")
        btn_delete.clicked.connect(self.on_delete)
        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.nav.goto_dashboard())
        h.addWidget(btn_back)
        h.addWidget(btn_delete)
        v.addLayout(h)
        self.setLayout(v)

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.class_input.setReadOnly(False)
            self.class_input.setStyleSheet("")
        else:
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def load_students(self):
        class_name = self.class_input.text().strip()
        if not class_name:
            show_error("Missing", "Provide class name.")
            return
        try:
            students = db.authenticate_user(class_name, AppState.get_class_password())
            container = QWidget()
            cv = QVBoxLayout()
            self.checkboxes.clear()
            for roll, name in students:
                cb = QCheckBox(f"{roll} — {name}")
                self.checkboxes[roll] = cb
                cv.addWidget(cb)
            container.setLayout(cv)
            self.scroll.setWidget(container)
            AppState.set_students(students)
            AppState.set_logged_class(class_name)
        except Exception as e:
            show_error("Load failed", str(e))

    def on_delete(self):
        selected = [r for r, cb in self.checkboxes.items() if cb.isChecked()]
        if not selected:
            show_info("No selection", "No students selected.")
            return
        class_name = self.class_input.text().strip()
        try:
            db.delete_data(class_name, selected)
            show_info("Deleted", f"Deleted {len(selected)} records from {class_name}.")
            # refresh
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            self.nav.goto_dashboard()
        except Exception as e:
            show_error("Delete failed", str(e))

# ---------- HistoryWidget ----------
class HistoryWidget(QWidget):
    """View attendance for a specific class and date."""
    def __init__(self, navigator):
        super().__init__()
        self.nav = navigator
        self.table = None
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout()
        v.setContentsMargins(60, 40, 60, 40)
        v.setSpacing(12)

        title = QLabel("Attendance History")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setProperty("role", "title")
        v.addWidget(title)

        row = QHBoxLayout()
        row.addWidget(QLabel("Class:"))
        self.class_input = QLineEdit()
        if AppState.get_logged_class():
            self.class_input.setText(AppState.get_logged_class())
        row.addWidget(self.class_input)

        row.addWidget(QLabel("Date:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(QDate.currentDate())
        row.addWidget(self.date_edit)

        btn_load = QPushButton("Load")
        btn_load.clicked.connect(self.load_history)
        row.addWidget(btn_load)
        v.addLayout(row)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Roll No", "Student Name", "Attendance"])
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        v.addWidget(self.table)

        btn_back = QPushButton("Back")
        btn_back.clicked.connect(lambda: self.nav.goto_dashboard())
        btn_export = QPushButton("Export CSV")
        btn_export.clicked.connect(self.export_csv)
        h2 = QHBoxLayout()
        h2.addWidget(btn_back)
        h2.addWidget(btn_export)
        v.addLayout(h2)

        self.setLayout(v)

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.class_input.setReadOnly(False)
            self.class_input.setStyleSheet("")
        else:
            self.class_input.setReadOnly(True)
            self.class_input.setStyleSheet("background-color:#f0f0f0; color:#555;")

    def load_history(self):
        class_name = self.class_input.text().strip()
        if not class_name:
            show_error("Missing", "Enter class name.")
            return
        date_qdate = self.date_edit.date()
        dt = datetime(date_qdate.year(), date_qdate.month(), date_qdate.day())
        colname = dt.strftime("%Y_%m_%d")
        try:
            db.connect()

            if not db._column_exists(class_name, colname):
                show_info("No data", f"No attendance recorded for {dt.strftime('%Y-%m-%d')} (column missing).")
                q = f"SELECT Roll_no, Student_name FROM `{class_name}` ORDER BY Roll_no;"
                db.cursor.execute(q)
                rows = db.cursor.fetchall()
                attendance_default = [(r[0], r[1], "Absent") for r in rows]
            else:
                q = f"SELECT Roll_no, Student_name, `{colname}` FROM `{class_name}` ORDER BY Roll_no;"
                db.cursor.execute(q)
                rows = db.cursor.fetchall()
                attendance_default = [(r[0], r[1], r[2] if r[2] is not None else "Absent") for r in rows]
            self.table.setRowCount(len(attendance_default))
            for r, (roll, name, att) in enumerate(attendance_default):
                it_roll = QTableWidgetItem(str(roll))
                it_roll.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                it_name = QTableWidgetItem(name)
                it_name.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                it_att = QTableWidgetItem(att)
                it_att.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled)
                self.table.setItem(r, 0, it_roll)
                self.table.setItem(r, 1, it_name)
                self.table.setItem(r, 2, it_att)
            AppState.set_logged_class(class_name)
            AppState.set_students([(row[0], row[1]) for row in attendance_default])
        except Exception as e:
            show_error("Load failed", str(e))

    def export_csv(self):
        if self.table.rowCount() == 0:
            show_info("No data", "No data to export.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export CSV", "", "CSV Files (*.csv)")
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(["Roll_no", "Student_name", "Attendance"])
                for r in range(self.table.rowCount()):
                    roll = self.table.item(r, 0).text()
                    name = self.table.item(r, 1).text()
                    att = self.table.item(r, 2).text()
                    writer.writerow([roll, name, att])
            show_info("Exported", f"Saved to {path}")
        except Exception as e:
            show_error("Export failed", str(e))

# ---------- Run ----------
def main():
    app = QApplication(sys.argv)
    win = Navigator()
    win.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()