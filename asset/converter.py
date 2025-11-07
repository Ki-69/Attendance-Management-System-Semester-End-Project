import mysql.connector
import sqlite3
from datetime import datetime
import hashlib

class MySQLToSQLiteMigrator:
    """
    Migrates data from MySQL attendance database to SQLite.
    """
    
    def __init__(self, mysql_config: dict, sqlite_db_path: str):
        """
        Initialize migrator.
        
        Args:
            mysql_config: Dict with keys: host, user, password, database
            sqlite_db_path: Path to SQLite database file
        """
        self.mysql_config = mysql_config
        self.sqlite_db_path = sqlite_db_path
        self.mysql_conn = None
        self.mysql_cursor = None
        self.sqlite_conn = None
        self.sqlite_cursor = None
    
    def connect_mysql(self):
        """Connect to MySQL database."""
        try:
            self.mysql_conn = mysql.connector.connect(**self.mysql_config)
            self.mysql_cursor = self.mysql_conn.cursor()
            print("✓ Connected to MySQL database")
        except mysql.connector.Error as e:
            raise ConnectionError(f"Failed to connect to MySQL: {e}")
    
    def connect_sqlite(self):
        """Connect to SQLite database."""
        try:
            self.sqlite_conn = sqlite3.connect(self.sqlite_db_path)
            self.sqlite_cursor = self.sqlite_conn.cursor()
            print(f"✓ Connected to SQLite database: {self.sqlite_db_path}")
        except sqlite3.Error as e:
            raise ConnectionError(f"Failed to connect to SQLite: {e}")
    
    def get_mysql_tables(self):
        """Get list of all tables from MySQL database."""
        self.mysql_cursor.execute("SHOW TABLES;")
        tables = [row[0] for row in self.mysql_cursor.fetchall()]
        # Exclude system tables if any
        return [t for t in tables if t != 'class_passwords']
    
    def get_table_columns(self, table_name: str):
        """Get column names and types for a MySQL table."""
        self.mysql_cursor.execute(f"DESCRIBE `{table_name}`;")
        columns = []
        for row in self.mysql_cursor.fetchall():
            col_name = row[0]
            col_type = row[1]
            # Convert MySQL types to SQLite types
            if 'int' in col_type.lower():
                sqlite_type = 'INTEGER'
            elif 'varchar' in col_type.lower() or 'text' in col_type.lower():
                sqlite_type = 'TEXT'
            elif 'date' in col_type.lower():
                sqlite_type = 'TEXT'
            else:
                sqlite_type = 'TEXT'
            
            columns.append((col_name, sqlite_type))
        return columns
    
    def create_sqlite_table(self, table_name: str, columns: list):
        """Create table in SQLite database."""
        # Build CREATE TABLE statement
        col_defs = []
        for col_name, col_type in columns:
            if col_name == 'Student_id':
                col_defs.append(f'"{col_name}" INTEGER PRIMARY KEY AUTOINCREMENT')
            elif col_name == 'Roll_no':
                col_defs.append(f'"{col_name}" {col_type} NOT NULL UNIQUE')
            elif col_name == 'Student_name':
                col_defs.append(f'"{col_name}" {col_type} NOT NULL')
            else:
                # Attendance columns
                col_defs.append(f'"{col_name}" {col_type} DEFAULT "Absent"')
        
        create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(col_defs)});'
        
        try:
            self.sqlite_cursor.execute(create_sql)
            self.sqlite_conn.commit()
            print(f"  ✓ Created table: {table_name}")
        except sqlite3.Error as e:
            print(f"  ✗ Error creating table {table_name}: {e}")
    
    def migrate_table_data(self, table_name: str):
        """Copy all data from MySQL table to SQLite table."""
        # Get all data from MySQL
        self.mysql_cursor.execute(f"SELECT * FROM `{table_name}`;")
        rows = self.mysql_cursor.fetchall()
        
        if not rows:
            print(f"  → No data in table {table_name}")
            return
        
        # Get column names
        columns = [desc[0] for desc in self.mysql_cursor.description]
        
        # Insert data into SQLite
        placeholders = ','.join(['?' for _ in columns])
        col_names = ','.join([f'"{col}"' for col in columns])
        insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders});'
        
        try:
            self.sqlite_cursor.executemany(insert_sql, rows)
            self.sqlite_conn.commit()
            print(f"  ✓ Migrated {len(rows)} rows to {table_name}")
        except sqlite3.Error as e:
            print(f"  ✗ Error migrating data to {table_name}: {e}")
    
    def migrate_passwords(self):
        """Migrate class passwords from MySQL to SQLite."""
        try:
            # Check if class_passwords table exists in MySQL
            self.mysql_cursor.execute("SHOW TABLES LIKE 'class_passwords';")
            if not self.mysql_cursor.fetchone():
                print("  → No class_passwords table found in MySQL")
                return
            
            # Create table in SQLite
            self.sqlite_cursor.execute("""
                CREATE TABLE IF NOT EXISTS class_passwords (
                    class_name TEXT PRIMARY KEY,
                    password_hash TEXT NOT NULL
                );
            """)
            
            # Copy data
            self.mysql_cursor.execute("SELECT class_name, password_hash FROM class_passwords;")
            rows = self.mysql_cursor.fetchall()
            
            if rows:
                self.sqlite_cursor.executemany(
                    "INSERT OR REPLACE INTO class_passwords (class_name, password_hash) VALUES (?, ?);",
                    rows
                )
                self.sqlite_conn.commit()
                print(f"  ✓ Migrated {len(rows)} class passwords")
            else:
                print("  → No class passwords to migrate")
                
        except Exception as e:
            print(f"  ✗ Error migrating passwords: {e}")
    
    def migrate_all(self):
        """Perform complete migration from MySQL to SQLite."""
        print("\n" + "="*60)
        print("MySQL to SQLite Migration Tool")
        print("="*60 + "\n")
        
        try:
            # Connect to both databases
            self.connect_mysql()
            self.connect_sqlite()
            
            # Migrate class passwords first
            print("\n[1] Migrating class passwords...")
            self.migrate_passwords()
            
            # Get all class tables
            print("\n[2] Getting list of class tables...")
            tables = self.get_mysql_tables()
            print(f"  Found {len(tables)} class tables: {', '.join(tables)}")
            
            # Migrate each table
            print("\n[3] Migrating class tables...")
            for i, table in enumerate(tables, 1):
                print(f"\n  [{i}/{len(tables)}] Processing table: {table}")
                
                # Get table structure
                columns = self.get_table_columns(table)
                
                # Create table in SQLite
                self.create_sqlite_table(table, columns)
                
                # Copy data
                self.migrate_table_data(table)
            
            print("\n" + "="*60)
            print("✓ Migration completed successfully!")
            print("="*60)
            print(f"\nSQLite database saved to: {self.sqlite_db_path}")
            print(f"Total tables migrated: {len(tables) + 1}")  # +1 for passwords
            
        except Exception as e:
            print(f"\n✗ Migration failed: {e}")
            raise
        
        finally:
            # Close connections
            if self.mysql_cursor:
                self.mysql_cursor.close()
            if self.mysql_conn:
                self.mysql_conn.close()
            if self.sqlite_cursor:
                self.sqlite_cursor.close()
            if self.sqlite_conn:
                self.sqlite_conn.close()
            print("\n✓ Database connections closed")


def main():
    """Run the migration."""
    
    # MySQL configuration - UPDATE THESE WITH YOUR CREDENTIALS
    mysql_config = {
        'host': 'localhost',
        'user': 'root',
        'password': 'tsukasa911',  # ← CHANGE THIS
        'database': 'attendance'
    }
    
    # SQLite database path
    sqlite_db_path = 'attendance.db'
    
    print("\nMySQL Configuration:")
    print(f"  Host: {mysql_config['host']}")
    print(f"  User: {mysql_config['user']}")
    print(f"  Database: {mysql_config['database']}")
    print(f"\nTarget SQLite: {sqlite_db_path}\n")
    
    response = input("Proceed with migration? (yes/no): ").strip().lower()
    if response != 'yes':
        print("Migration cancelled.")
        return
    
    # Create migrator and run
    migrator = MySQLToSQLiteMigrator(mysql_config, sqlite_db_path)
    migrator.migrate_all()


if __name__ == "__main__":
    main()