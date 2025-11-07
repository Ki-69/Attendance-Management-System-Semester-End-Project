import sys
import csv
import re
from datetime import datetime
from typing import List, Tuple, Optional

import Main_database as dbmod

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.checkbox import CheckBox
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.uix.spinner import Spinner
from kivy.properties import StringProperty, BooleanProperty, ListProperty
from kivy.metrics import dp
from kivy.clock import Clock

# ---------- CONFIG ----------
# For Android, use internal storage path
DB_PATH = "attendance.db"  # SQLite database file
ADMIN_PASSWORD = "123"

# instantiate DB wrapper
db = dbmod.AttendanceDB(
    db_path=DB_PATH,
    admin_password=ADMIN_PASSWORD,
)

# ---------- Small utilities ----------
def show_error(title: str, msg: str):
    popup = Popup(title=title,
                content=Label(text=msg, color=(0, 0, 0, 1)),
                size_hint=(0.6, 0.4))
    popup.open()

def show_info(title: str, msg: str):
    popup = Popup(title=title,
                content=Label(text=msg, color=(0, 0, 0, 1)),
                size_hint=(0.6, 0.4))
    popup.open()

def is_valid_identifier(name: str) -> bool:
    return bool(re.match(r"^[A-Za-z][A-Za-z0-9_]*$", name))

# ---------- Transient state manager ----------
class AppState:
    """Holds last_logged_in_class and last_student_list (Roll_no,name)"""
    last_logged_in_class: Optional[str] = None
    last_student_list: List[Tuple[int, str]] = []
    last_absent_list: List[int] = []
    last_class_password: Optional[str] = None
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

    @classmethod
    def set_is_admin(cls, value: bool):
        cls.is_admin = bool(value)

    @classmethod
    def is_admin_user(cls) -> bool:
        return bool(cls.is_admin)

# ---------- Login Screen ----------
class LoginScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'login'

    def on_login(self):
        class_name = self.ids.class_input.text.strip()
        password = self.ids.password_input.text.strip()

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
                students = db.authenticate_user(class_name, password)
                AppState.set_is_admin(False)
                AppState.set_logged_class(class_name)
                AppState.set_class_password(password)
                AppState.set_students(students)

            self.manager.current = 'dashboard'
            self.manager.get_screen('dashboard').refresh()

        except Exception as e:
            show_error("Login failed", str(e))

    def on_create_class(self):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        class_input = TextInput(hint_text='Enter new class name', multiline=False, foreground_color=(0, 0, 0, 1))
        content.add_widget(class_input)
        
        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)
        btn_ok = Button(text='OK')
        btn_cancel = Button(text='Cancel')
        btn_layout.add_widget(btn_ok)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Create Class', content=content, size_hint=(0.6, 0.4))
        
        def on_ok(instance):
            class_name = class_input.text.strip()
            if not class_name:
                popup.dismiss()
                return
            if not is_valid_identifier(class_name):
                popup.dismiss()
                show_error("Invalid Name", "Class name must start with a letter and contain only letters, digits, underscores.")
                return
            
            try:
                db.create_table_for_class(class_name)
                popup.dismiss()
                self.ask_password(class_name)
            except Exception as e:
                popup.dismiss()
                show_error("Create failed", str(e))
        
        btn_ok.bind(on_press=on_ok)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

    def ask_password(self, class_name):
        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        pw_input = TextInput(hint_text='Enter password', multiline=False, password=True, foreground_color=(0, 0, 0, 1))
        content.add_widget(pw_input)
        
        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)
        btn_ok = Button(text='OK')
        btn_cancel = Button(text='Cancel')
        btn_layout.add_widget(btn_ok)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Set Class Password', content=content, size_hint=(0.6, 0.4))
        
        def on_ok(instance):
            pw = pw_input.text.strip()
            if pw:
                db.set_class_password(class_name, pw)
                show_info("Created", f"Class '{class_name}' created with its own password.")
            else:
                show_info("Created", f"Class '{class_name}' created, but no password set yet.")
            self.ids.class_input.text = class_name
            popup.dismiss()
        
        btn_ok.bind(on_press=on_ok)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

# ---------- Dashboard Screen ----------
class DashboardScreen(Screen):
    class_name = StringProperty("")
    current_date = StringProperty("")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'dashboard'
        self.current_date = datetime.now().strftime("%Y-%m-%d")

    def refresh(self):
        class_name = AppState.get_logged_class()
        self.class_name = class_name if class_name else "(none)"
        
        students = AppState.get_students()
        self.ids.preview_list.clear_widgets()
        for roll, name in students[:50]:
            lbl = Label(text=f"{roll} — {name}", size_hint_y=None, height=dp(30), color=(0, 0, 0, 1))
            self.ids.preview_list.add_widget(lbl)

    def on_mark_all_present(self):
        class_name = AppState.get_logged_class()
        if not class_name:
            show_error("Not logged in", "Please login first.")
            self.manager.current = 'login'
            return

        dt = datetime.now()
        try:
            db.mark_all_present(class_name, dt)
            show_info("Success", f"All students marked Present on {dt.strftime('%Y-%m-%d')}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            AppState.set_absent([])
        except Exception as e:
            show_error("Failed", str(e))

    def on_logout(self):
        AppState.set_is_admin(False)
        AppState.set_logged_class(None)
        AppState.set_students([])
        AppState.set_absent([])
        self.manager.current = 'login'

# ---------- Display Screen ----------
class DisplayScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'display'
        self.table_data = []

    def on_pre_enter(self):
        class_name = AppState.get_logged_class()
        if class_name:
            self.ids.class_input.text = class_name
        self.ids.date_input.text = datetime.now().strftime("%Y-%m-%d")
        self.apply_admin_state()

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.ids.class_input.readonly = False
            self.ids.class_input.background_color = (1, 1, 1, 1)
        else:
            self.ids.class_input.readonly = True
            self.ids.class_input.background_color = (0.94, 0.94, 0.94, 1)

    def load_table_for_date(self):
        class_name = self.ids.class_input.text.strip()
        if not class_name:
            show_error("Missing", "Provide class name.")
            return
        if not is_valid_identifier(class_name):
            show_error("Invalid", "Class name must be valid identifier.")
            return

        date_str = self.ids.date_input.text.strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            show_error("Invalid date", "Use YYYY-MM-DD format.")
            return

        colname = dt.strftime("%Y_%m_%d")

        try:
            db.connect()
            if not db._column_exists(class_name, colname):
                db.cursor.execute(
                    f'ALTER TABLE "{class_name}" ADD COLUMN "{colname}" TEXT DEFAULT "Absent";'
                )
                db.conn.commit()

            q = f'SELECT Roll_no, Student_name, "{colname}" FROM "{class_name}" ORDER BY Roll_no;'
            db.cursor.execute(q)
            rows = db.cursor.fetchall()

            self.table_data = []
            table_container = self.ids.table_container
            table_container.clear_widgets()

            for row in rows:
                roll = row[0]
                name = row[1] if row[1] is not None else ""
                att = row[2] if row[2] is not None else "Absent"
                
                self.table_data.append({'roll': roll, 'name': name, 'present': att.lower() == 'present'})
                
                row_layout = BoxLayout(size_hint_y=None, height=dp(40), spacing=10)
                
                roll_label = Label(text=str(roll), size_hint_x=0.2, color=(0, 0, 0, 1))
                name_input = TextInput(text=name, multiline=False, size_hint_x=0.5, foreground_color=(0, 0, 0, 1))
                checkbox = CheckBox(active=att.lower() == 'present', size_hint_x=0.3)
                
                row_layout.add_widget(roll_label)
                row_layout.add_widget(name_input)
                row_layout.add_widget(checkbox)
                
                table_container.add_widget(row_layout)

            AppState.set_logged_class(class_name)
            AppState.set_students([(row[0], row[1]) for row in rows])

        except Exception as e:
            show_error("Load failed", str(e))

    def save_changes(self):
        class_name = self.ids.class_input.text.strip()
        if not class_name:
            show_error("Missing", "Provide class name.")
            return

        date_str = self.ids.date_input.text.strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            show_error("Invalid date", "Use YYYY-MM-DD format.")
            return

        colname = dt.strftime("%Y_%m_%d")

        table_container = self.ids.table_container
        if len(table_container.children) == 0:
            show_info("No data", "Nothing to save.")
            return

        try:
            db.connect()
            if not db._column_exists(class_name, colname):
                db.cursor.execute(
                    f'ALTER TABLE "{class_name}" ADD COLUMN "{colname}" TEXT DEFAULT "Absent";'
                )
                db.conn.commit()

            for row_widget in reversed(table_container.children):
                roll_label = row_widget.children[2]
                name_input = row_widget.children[1]
                checkbox = row_widget.children[0]
                
                roll = int(roll_label.text)
                name_val = name_input.text.strip()
                att_val = "Present" if checkbox.active else "Absent"

                if name_val:
                    db.cursor.execute(
                        f'UPDATE "{class_name}" SET Student_name=? WHERE Roll_no=?;',
                        (name_val, roll),
                    )

                db.cursor.execute(
                    f'UPDATE "{class_name}" SET "{colname}"=? WHERE Roll_no=?;',
                    (att_val, roll),
                )

            db.conn.commit()
            show_info("Saved", "Changes saved to database.")

        except Exception as e:
            show_error("Save failed", str(e))

    def export_csv(self):
        table_container = self.ids.table_container
        if len(table_container.children) == 0:
            show_info("No data", "No table data to export.")
            return

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        file_input = TextInput(hint_text='Enter filename (e.g., attendance.csv)', multiline=False, foreground_color=(0, 0, 0, 1))
        content.add_widget(file_input)
        
        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)
        btn_save = Button(text='Save')
        btn_cancel = Button(text='Cancel')
        btn_layout.add_widget(btn_save)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Export CSV', content=content, size_hint=(0.6, 0.4))
        
        def on_save(instance):
            path = file_input.text.strip()
            if not path:
                popup.dismiss()
                return
            
            try:
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["Roll_no", "Student_name", "Attendance"])
                    for row_widget in reversed(table_container.children):
                        roll = row_widget.children[2].text
                        name = row_widget.children[1].text
                        att = "Present" if row_widget.children[0].active else "Absent"
                        writer.writerow([roll, name, att])
                popup.dismiss()
                show_info("Exported", f"Exported to {path}")
            except Exception as e:
                popup.dismiss()
                show_error("Export failed", str(e))
        
        btn_save.bind(on_press=on_save)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

# ---------- Select Absent Screen ----------
class SelectAbsentScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'select_absent'
        self.checkboxes = {}

    def on_pre_enter(self):
        class_name = AppState.get_logged_class()
        if class_name:
            self.ids.class_input.text = class_name
        self.ids.date_input.text = datetime.now().strftime("%Y-%m-%d")
        self.apply_admin_state()

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.ids.class_input.readonly = False
            self.ids.class_input.background_color = (1, 1, 1, 1)
        else:
            self.ids.class_input.readonly = True
            self.ids.class_input.background_color = (0.94, 0.94, 0.94, 1)

    def load_students(self):
        class_name = self.ids.class_input.text.strip()
        if not class_name:
            show_error("Missing", "Enter class name.")
            return
        if not is_valid_identifier(class_name):
            show_error("Invalid", "Class name invalid.")
            return
        try:
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)

            container = self.ids.students_container
            container.clear_widgets()
            self.checkboxes.clear()
            
            for roll, name in students:
                row = BoxLayout(size_hint_y=None, height=dp(35), spacing=5)
                cb = CheckBox(size_hint_x=0.1)
                lbl = Label(text=f"{roll} — {name}", size_hint_x=0.9, color=(0, 0, 0, 1))
                row.add_widget(cb)
                row.add_widget(lbl)
                self.checkboxes[roll] = cb
                container.add_widget(row)
            
            AppState.set_logged_class(class_name)
        except Exception as e:
            show_error("Load failed", str(e))

    def clear_selection(self):
        for cb in self.checkboxes.values():
            cb.active = False

    def mark_selected_absent(self):
        selected = [r for r, cb in self.checkboxes.items() if cb.active]
        if not selected:
            show_info("No selection", "No students selected.")
            return
        
        class_name = self.ids.class_input.text.strip()
        date_str = self.ids.date_input.text.strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            show_error("Invalid date", "Use YYYY-MM-DD format.")
            return

        try:
            if not db._column_exists(class_name, dt.strftime("%Y_%m_%d")):
                db.cursor.execute(f'ALTER TABLE "{class_name}" ADD COLUMN "{dt.strftime("%Y_%m_%d")}" TEXT DEFAULT "Absent";')
                db.conn.commit()
            db.custom_marking_absent(class_name, selected, dt)
            AppState.set_absent(selected)
            show_info("Marked", f"Marked {len(selected)} students absent for {dt.strftime('%Y-%m-%d')}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
        except Exception as e:
            show_error("Mark failed", str(e))

# ---------- Add Student Screen ----------
class AddStudentScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'add_student'

    def on_pre_enter(self):
        class_name = AppState.get_logged_class()
        if class_name:
            self.ids.class_input.text = class_name
        self.apply_admin_state()

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.ids.class_input.readonly = False
            self.ids.class_input.background_color = (1, 1, 1, 1)
        else:
            self.ids.class_input.readonly = True
            self.ids.class_input.background_color = (0.94, 0.94, 0.94, 1)

    def on_add(self):
        name = self.ids.name_input.text.strip()
        roll_str = self.ids.roll_input.text.strip()
        class_name = self.ids.class_input.text.strip()
        
        if not name or not class_name or not roll_str:
            show_error("Missing", "Provide student name, roll number, and class.")
            return
        
        try:
            roll = int(roll_str)
        except:
            show_error("Invalid", "Roll number must be a number.")
            return

        try:
            db.add_individual(class_name, name, roll)
            show_info("Added", f"{name} added to {class_name}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            AppState.set_logged_class(class_name)
            self.manager.current = 'dashboard'
            self.manager.get_screen('dashboard').refresh()
        except Exception as e:
            show_error("Add failed", str(e))

# ---------- Import CSV Screen ----------
class ImportCSVScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'import_csv'

    def on_pre_enter(self):
        class_name = AppState.get_logged_class()
        if class_name:
            self.ids.class_input.text = class_name
        self.apply_admin_state()

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.ids.class_input.readonly = False
            self.ids.class_input.background_color = (1, 1, 1, 1)
        else:
            self.ids.class_input.readonly = True
            self.ids.class_input.background_color = (0.94, 0.94, 0.94, 1)

    def browse(self):
        content = BoxLayout(orientation='vertical')
        file_chooser = FileChooserListView(filters=['*.csv'])
        content.add_widget(file_chooser)
        
        btn_layout = BoxLayout(size_hint_y=0.1, spacing=10)
        btn_select = Button(text='Select')
        btn_cancel = Button(text='Cancel')
        btn_layout.add_widget(btn_select)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Select CSV File', content=content, size_hint=(0.9, 0.9))
        
        def on_select(instance):
            if file_chooser.selection:
                self.ids.file_input.text = file_chooser.selection[0]
            popup.dismiss()
        
        btn_select.bind(on_press=on_select)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

    def on_import(self):
        path = self.ids.file_input.text.strip()
        class_name = self.ids.class_input.text.strip()
        if not path or not class_name:
            show_error("Missing", "Provide file path and class name.")
            return
        try:
            db.add_data_from_csv(path, class_name)
            show_info("Imported", f"CSV imported into {class_name}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            AppState.set_logged_class(class_name)
            self.manager.current = 'dashboard'
            self.manager.get_screen('dashboard').refresh()
        except Exception as e:
            show_error("Import failed", str(e))

# ---------- Delete Screen ----------
class DeleteScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'delete'
        self.checkboxes = {}

    def on_pre_enter(self):
        class_name = AppState.get_logged_class()
        if class_name:
            self.ids.class_input.text = class_name
        self.apply_admin_state()

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.ids.class_input.readonly = False
            self.ids.class_input.background_color = (1, 1, 1, 1)
        else:
            self.ids.class_input.readonly = True
            self.ids.class_input.background_color = (0.94, 0.94, 0.94, 1)

    def load_students(self):
        class_name = self.ids.class_input.text.strip()
        if not class_name:
            show_error("Missing", "Provide class name.")
            return
        try:
            students = db.authenticate_user(class_name, AppState.get_class_password())
            container = self.ids.students_container
            container.clear_widgets()
            self.checkboxes.clear()
            
            for roll, name in students:
                row = BoxLayout(size_hint_y=None, height=dp(35), spacing=5)
                cb = CheckBox(size_hint_x=0.1)
                lbl = Label(text=f"{roll} — {name}", size_hint_x=0.9, color=(0, 0, 0, 1))
                row.add_widget(cb)
                row.add_widget(lbl)
                self.checkboxes[roll] = cb
                container.add_widget(row)
            
            AppState.set_students(students)
            AppState.set_logged_class(class_name)
        except Exception as e:
            show_error("Load failed", str(e))

    def on_delete(self):
        selected = [r for r, cb in self.checkboxes.items() if cb.active]
        if not selected:
            show_info("No selection", "No students selected.")
            return
        class_name = self.ids.class_input.text.strip()
        try:
            db.delete_data(class_name, selected)
            show_info("Deleted", f"Deleted {len(selected)} records from {class_name}.")
            students = db.authenticate_user(class_name, AppState.get_class_password())
            AppState.set_students(students)
            self.manager.current = 'dashboard'
            self.manager.get_screen('dashboard').refresh()
        except Exception as e:
            show_error("Delete failed", str(e))

# ---------- History Screen ----------
class HistoryScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name = 'history'

    def on_pre_enter(self):
        class_name = AppState.get_logged_class()
        if class_name:
            self.ids.class_input.text = class_name
        self.ids.date_input.text = datetime.now().strftime("%Y-%m-%d")
        self.apply_admin_state()

    def apply_admin_state(self):
        if AppState.is_admin_user():
            self.ids.class_input.readonly = False
            self.ids.class_input.background_color = (1, 1, 1, 1)
        else:
            self.ids.class_input.readonly = True
            self.ids.class_input.background_color = (0.94, 0.94, 0.94, 1)

    def load_history(self):
        class_name = self.ids.class_input.text.strip()
        if not class_name:
            show_error("Missing", "Enter class name.")
            return
        
        date_str = self.ids.date_input.text.strip()
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except:
            show_error("Invalid date", "Use YYYY-MM-DD format.")
            return

        colname = dt.strftime("%Y_%m_%d")
        try:
            db.connect()

            if not db._column_exists(class_name, colname):
                show_info("No data", f"No attendance recorded for {dt.strftime('%Y-%m-%d')} (column missing).")
                q = f'SELECT Roll_no, Student_name FROM "{class_name}" ORDER BY Roll_no;'
                db.cursor.execute(q)
                rows = db.cursor.fetchall()
                attendance_default = [(r[0], r[1], "Absent") for r in rows]
            else:
                q = f'SELECT Roll_no, Student_name, "{colname}" FROM "{class_name}" ORDER BY Roll_no;'
                db.cursor.execute(q)
                rows = db.cursor.fetchall()
                attendance_default = [(r[0], r[1], r[2] if r[2] is not None else "Absent") for r in rows]
            
            container = self.ids.history_container
            container.clear_widgets()
            
            for roll, name, att in attendance_default:
                row = BoxLayout(size_hint_y=None, height=dp(35), spacing=10)
                roll_lbl = Label(text=str(roll), size_hint_x=0.2, color=(0, 0, 0, 1))
                name_lbl = Label(text=name, size_hint_x=0.5, color=(0, 0, 0, 1))
                att_lbl = Label(text=att, size_hint_x=0.3, color=(0, 0, 0, 1))
                row.add_widget(roll_lbl)
                row.add_widget(name_lbl)
                row.add_widget(att_lbl)
                container.add_widget(row)
            
            AppState.set_logged_class(class_name)
            AppState.set_students([(row[0], row[1]) for row in attendance_default])
        except Exception as e:
            show_error("Load failed", str(e))

    def export_csv(self):
        container = self.ids.history_container
        if len(container.children) == 0:
            show_info("No data", "No data to export.")
            return

        content = BoxLayout(orientation='vertical', spacing=10, padding=10)
        file_input = TextInput(hint_text='Enter filename (e.g., history.csv)', multiline=False, foreground_color=(0, 0, 0, 1))
        content.add_widget(file_input)
        
        btn_layout = BoxLayout(size_hint_y=0.3, spacing=10)
        btn_save = Button(text='Save')
        btn_cancel = Button(text='Cancel')
        btn_layout.add_widget(btn_save)
        btn_layout.add_widget(btn_cancel)
        content.add_widget(btn_layout)
        
        popup = Popup(title='Export CSV', content=content, size_hint=(0.6, 0.4))
        
        def on_save(instance):
            path = file_input.text.strip()
            if not path:
                popup.dismiss()
                return
            
            try:
                with open(path, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.writer(fh)
                    writer.writerow(["Roll_no", "Student_name", "Attendance"])
                    for row_widget in reversed(container.children):
                        roll = row_widget.children[2].text
                        name = row_widget.children[1].text
                        att = row_widget.children[0].text
                        writer.writerow([roll, name, att])
                popup.dismiss()
                show_info("Exported", f"Saved to {path}")
            except Exception as e:
                popup.dismiss()
                show_error("Export failed", str(e))
        
        btn_save.bind(on_press=on_save)
        btn_cancel.bind(on_press=popup.dismiss)
        popup.open()

# ---------- Main App ----------
class AttendanceApp(App):
    def build(self):
        try:
            db.connect()
        except Exception as e:
            show_error("DB Connect", f"Could not connect at startup: {e}")
        
        sm = ScreenManager()
        sm.add_widget(LoginScreen())
        sm.add_widget(DashboardScreen())
        sm.add_widget(DisplayScreen())
        sm.add_widget(SelectAbsentScreen())
        sm.add_widget(AddStudentScreen())
        sm.add_widget(ImportCSVScreen())
        sm.add_widget(DeleteScreen())
        sm.add_widget(HistoryScreen())
        return sm

if __name__ == "__main__":
    AttendanceApp().run()