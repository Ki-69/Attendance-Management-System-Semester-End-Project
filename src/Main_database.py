import sqlite3
from datetime import datetime
import csv
import re
from typing import List, Iterable, Optional
import hashlib
import os

class AttendanceDB:
    IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")

    def __init__(self, db_path: str = "attendance.db", admin_password: str = "123"):
        """
        Initialize SQLite database connection.
        
        Args:
            db_path: Path to SQLite database file (default: attendance.db)
            admin_password: Master admin password for override access
        """
        self.db_path = db_path
        self.admin_password = admin_password
        self.conn: Optional[sqlite3.Connection] = None
        self.cursor: Optional[sqlite3.Cursor] = None

    def _validate_identifier(self, name: str) -> None:
        """Ensure table/column identifier is safe (letters, digits, underscores; starts with letter)."""
        if not isinstance(name, str) or not name:
            raise ValueError("Identifier must be a non-empty string.")
        if not self.IDENTIFIER_RE.match(name):
            raise ValueError(f"Invalid identifier: {name!r}. Allowed: letters, digits, underscore; must start with a letter.")

    def _date_column_name(self, dt: Optional[datetime] = None) -> str:
        dt = dt or datetime.now()
        return dt.strftime("%Y_%m_%d")

    def connect(self) -> bool:
        """Open connection and cursor if not already open. Returns True on success."""
        if self.conn is not None:
            return True
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            # Enable foreign keys
            self.cursor.execute("PRAGMA foreign_keys = ON;")
            return True
        except sqlite3.Error as e:
            raise ConnectionError(f"Error connecting to the database: {e}") from e

    def close(self) -> None:
        if self.cursor:
            try:
                self.cursor.close()
            except Exception:
                pass
            self.cursor = None
        if self.conn:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    # Table operations
    def store_table_names(self) -> List[str]:
        """Return list of tables (class names) in the current database."""
        self.connect()
        self.cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name != 'class_passwords'
            ORDER BY name;
        """)
        rows = self.cursor.fetchall()
        return [r[0] for r in rows]

    def create_table_for_class(self, class_name: str) -> None:
        """Create a new class table with auto-increment student id and unique roll_no."""
        self._validate_identifier(class_name)
        self.connect()
        query = f"""
        CREATE TABLE IF NOT EXISTS "{class_name}" (
            Student_id INTEGER PRIMARY KEY AUTOINCREMENT,
            Student_name TEXT NOT NULL,
            Roll_no INTEGER NOT NULL UNIQUE
        );
        """
        self.cursor.execute(query)
        self.conn.commit()

    # Authentication
    def _hash_password(self, password: str) -> str:
        """Hash password with SHA256 for storage."""
        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def set_class_password(self, class_name: str, password: str) -> None:
        """Set or update the password for a specific class."""
        self._validate_identifier(class_name)
        self.connect()
        pw_hash = self._hash_password(password)
        
        # Create password table if not exists
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS class_passwords (
                class_name TEXT PRIMARY KEY,
                password_hash TEXT NOT NULL
            );
        """)
        
        # Insert or replace password
        self.cursor.execute("""
            INSERT OR REPLACE INTO class_passwords (class_name, password_hash)
            VALUES (?, ?);
        """, (class_name, pw_hash))
        self.conn.commit()

    def get_class_password_hash(self, class_name: str) -> Optional[str]:
        """Fetch the stored password hash for a class."""
        self._validate_identifier(class_name)
        self.connect()
        self.cursor.execute("""
            SELECT password_hash FROM class_passwords WHERE class_name=?;
        """, (class_name,))
        row = self.cursor.fetchone()
        return row[0] if row else None

    def authenticate_user(self, class_name: str, password: str) -> list[tuple]:
        """
        Authenticate by verifying class_name exists and password matches either:
        - the stored per-class password, or
        - the global admin_password (master override).
        Returns list of (Roll_no, Student_name) tuples on success.
        Raises ValueError on failure.
        """
        self._validate_identifier(class_name)
        self.connect()

        if class_name not in self.store_table_names():
            raise ValueError(f"Authentication failed: class/table '{class_name}' not found.")

        # Admin password override
        if password == self.admin_password:
            query = f'SELECT Roll_no, Student_name FROM "{class_name}" ORDER BY Roll_no;'
            self.cursor.execute(query)
            return self.cursor.fetchall()

        # Check class-specific password
        stored_hash = self.get_class_password_hash(class_name)
        if stored_hash is None:
            raise ValueError(f"No password set for class '{class_name}'. Please set one.")
        if stored_hash != self._hash_password(password):
            raise ValueError("Authentication failed: incorrect password.")

        query = f'SELECT Roll_no, Student_name FROM "{class_name}" ORDER BY Roll_no;'
        self.cursor.execute(query)
        return self.cursor.fetchall()

    # Column (date) management
    def _column_exists(self, table: str, column: str) -> bool:
        """Return True if column exists in table."""
        self.connect()
        self.cursor.execute(f'PRAGMA table_info("{table}");')
        columns = [row[1] for row in self.cursor.fetchall()]
        return column in columns

    def add_columns_for_today(self, dt: Optional[datetime] = None) -> None:
        """
        Add a date column (YYYY_MM_DD) to every class table for attendance,
        skipping weekends (Saturday=5, Sunday=6).
        """
        dt = dt or datetime.now()
        weekday = dt.weekday()
        if weekday in (5, 6):
            return

        col = self._date_column_name(dt)
        tables = self.store_table_names()
        
        for table in tables:
            self._validate_identifier(table)
            try:
                if not self._column_exists(table, col):
                    alter = f'ALTER TABLE "{table}" ADD COLUMN "{col}" TEXT DEFAULT "Absent";'
                    self.cursor.execute(alter)
                    self.conn.commit()
            except sqlite3.Error as e:
                raise RuntimeError(f"Failed to add column {col} to {table}: {e}") from e

    # Marking attendance
    def mark_all_present(self, class_name: str, dt: Optional[datetime] = None) -> None:
        """Mark every student in class_name as 'Present' for the provided date (default: today)."""
        self._validate_identifier(class_name)
        col = self._date_column_name(dt)
        self.connect()

        if not self._column_exists(class_name, col):
            self.cursor.execute(f'ALTER TABLE "{class_name}" ADD COLUMN "{col}" TEXT DEFAULT "Absent";')
            self.conn.commit()

        update = f'UPDATE "{class_name}" SET "{col}" = ?;'
        self.cursor.execute(update, ("Present",))
        self.conn.commit()

    def custom_marking_absent(self, class_name: str, absent_rolls: Iterable[int], dt: Optional[datetime] = None) -> None:
        """
        Mark specific roll numbers as 'Absent' for the given date (default: today).
        absent_rolls should be an iterable of integers.
        """
        self._validate_identifier(class_name)
        rolls = list(absent_rolls)
        if not rolls:
            return

        col = self._date_column_name(dt)
        self.connect()
        
        if not self._column_exists(class_name, col):
            self.cursor.execute(f'ALTER TABLE "{class_name}" ADD COLUMN "{col}" TEXT DEFAULT "Absent";')
            self.conn.commit()

        placeholders = ",".join(["?"] * len(rolls))
        query = f'UPDATE "{class_name}" SET "{col}" = ? WHERE Roll_no IN ({placeholders});'
        params = ["Absent"] + rolls
        self.cursor.execute(query, tuple(params))
        self.conn.commit()

    # Inserts / deletes
    def add_data_from_csv(self, path: str, class_name: str, has_header: bool = False) -> None:
        """Insert rows from CSV file (Student_name, Roll_no). Uses INSERT OR REPLACE to update name if roll exists."""
        self._validate_identifier(class_name)
        self.connect()
        self.create_table_for_class(class_name)

        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.reader(fh)
            if has_header:
                next(reader, None)
            rows_to_insert = []
            for row in reader:
                if not row:
                    continue
                if len(row) < 2:
                    raise ValueError(f"CSV row must have at least 2 columns: {row}")
                name = row[0].strip()
                roll = int(row[1])
                rows_to_insert.append((name, roll))

            if not rows_to_insert:
                return

            # SQLite doesn't have ON DUPLICATE KEY UPDATE, so we use INSERT OR REPLACE
            # But we need to preserve Student_id, so we first check if exists
            for name, roll in rows_to_insert:
                self.cursor.execute(f"""
                    INSERT INTO "{class_name}" (Student_name, Roll_no)
                    VALUES (?, ?)
                    ON CONFLICT(Roll_no) DO UPDATE SET Student_name = excluded.Student_name;
                """, (name, roll))
            
            self.conn.commit()

    def add_individual(self, class_name: str, student_name: str, roll_no: int) -> None:
        """Insert one student row; if roll exists update name."""
        self._validate_identifier(class_name)
        self.connect()
        self.create_table_for_class(class_name)
        
        query = f"""
        INSERT INTO "{class_name}" (Student_name, Roll_no)
        VALUES (?, ?)
        ON CONFLICT(Roll_no) DO UPDATE SET Student_name = excluded.Student_name;
        """
        self.cursor.execute(query, (student_name, int(roll_no)))
        self.conn.commit()

    def delete_data(self, class_name: str, roll_nos: Iterable[int]) -> None:
        """Delete specific roll numbers from class table."""
        self._validate_identifier(class_name)
        rolls = list(roll_nos)
        if not rolls:
            return
        self.connect()
        placeholders = ",".join(["?"] * len(rolls))
        query = f'DELETE FROM "{class_name}" WHERE Roll_no IN ({placeholders});'
        self.cursor.execute(query, tuple(rolls))
        self.conn.commit()

    def delete_all(self, class_name: str) -> None:
        """Delete every student row in the class (keeps table schema)."""
        self._validate_identifier(class_name)
        self.connect()
        query = f'DELETE FROM "{class_name}";'
        self.cursor.execute(query)
        self.conn.commit()


if __name__ == "__main__":
    # Example usage
    db = AttendanceDB("attendance.db", admin_password="123")

    try:
        db.connect()
        print("✓ Connected to SQLite database")
        
        # Test creating a class
        db.create_table_for_class("TestClass")
        print("✓ Created test class table")
        
        # Test setting password
        db.set_class_password("TestClass", "test123")
        print("✓ Set class password")
        
        # Test adding student
        db.add_individual("TestClass", "John Doe", 101)
        print("✓ Added student")
        
        # Test authentication
        students = db.authenticate_user("TestClass", "test123")
        print(f"✓ Authenticated and retrieved {len(students)} students")
        
        db.close()
        print("✓ Database operations completed successfully")
        
    except Exception as e:
        print(f"✗ Error: {e}")