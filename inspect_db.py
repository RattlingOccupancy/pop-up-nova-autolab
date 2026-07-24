import sqlite3
import os
import glob

def inspect_database(db_path):
    print(f"\n==========================================")
    print(f"Inspecting: {db_path}")
    print(f"==========================================")
    if not os.path.exists(db_path):
        print("File does not exist.")
        return
        
    try:
        # Connect in read-only mode to avoid locks
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        
        # Get tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables found: {tables}")
        
        for table in tables:
            print(f"\n--- Table: {table} ---")
            # Get table schema
            cursor.execute(f"PRAGMA table_info({table});")
            columns = [col[1] for col in cursor.fetchall()]
            print(f"Columns: {columns}")
            
            # Fetch latest 2 rows to see the values
            try:
                cursor.execute(f"SELECT * FROM {table} ORDER BY rowid DESC LIMIT 2;")
                rows = cursor.fetchall()
                if rows:
                    print("Latest Rows:")
                    for row in rows:
                        print(dict(zip(columns, row)))
                else:
                    print("Table is empty.")
            except Exception as e:
                # Some tables might not support ORDER BY rowid or be system tables
                try:
                    cursor.execute(f"SELECT * FROM {table} LIMIT 2;")
                    rows = cursor.fetchall()
                    if rows:
                        print("Sample Rows:")
                        for row in rows:
                            print(dict(zip(columns, row)))
                    else:
                        print("Table is empty.")
                except Exception as ex:
                    print(f"Could not read table data: {ex}")
        conn.close()
    except Exception as e:
        print(f"Failed to read database: {e}")

def main():
    # Scan standard Nova directory for active sqlite files
    search_dir = r"C:\Users\Public\Documents\Metrohm Autolab\NOVA 2.1\Database"
    print(f"Scanning for SQLite files in {search_dir}...")
    
    files = glob.glob(os.path.join(search_dir, "**", "*.sqlite"), recursive=True)
    if not files:
        print("No SQLite files found in standard Nova directory.")
        # Try local folder too
        files = glob.glob("*.sqlite")
        
    for idx, f in enumerate(files):
        print(f"[{idx}] {f}")
        
    if files:
        selection = input("\nEnter the number of the database you want to inspect (or press Enter to inspect all): ")
        if selection.strip():
            try:
                idx = int(selection)
                inspect_database(files[idx])
            except (ValueError, IndexError):
                print("Invalid selection.")
        else:
            for f in files:
                inspect_database(f)

if __name__ == "__main__":
    main()
