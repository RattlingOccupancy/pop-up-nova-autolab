import sqlite3
import threading
import time
import json
import urllib.parse
import os

class NovaDataMonitor(threading.Thread):
    def __init__(self, config_path, update_callback, error_callback):
        super().__init__()
        self.daemon = True
        self.config_path = config_path
        self.update_callback = update_callback
        self.error_callback = error_callback
        
        self.running = True
        
        # Load initial config
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            self.error_callback(f"Failed to load config: {e}")
            self.config = {
                "sqlite_db_path": "C:\\temp_nova_data.sqlite",
                "poll_interval_seconds": 1.0,
                "sqlite_query": "SELECT * FROM measurement_data ORDER BY id DESC LIMIT 1;"
            }

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                self._load_config()
                db_path = self.config.get("sqlite_db_path", "")
                if not os.path.isabs(db_path):
                    # Resolve relative to the config file's directory
                    config_dir = os.path.dirname(os.path.abspath(self.config_path))
                    db_path = os.path.join(config_dir, db_path)
                
                # Auto-detect latest modified SQLite file if a directory is provided
                candidate_paths = []
                if os.path.isdir(db_path):
                    import glob
                    # Search for idf.sqlite, tmp.sqlite, raw.sqlite, and general sqlite files
                    found_files = set()
                    for pattern in ["**/*.idf.sqlite", "**/*.tmp.sqlite", "**/*.raw.sqlite", "**/*.sqlite"]:
                        for f in glob.glob(os.path.join(db_path, pattern), recursive=True):
                            found_files.add(f)
                    
                    if found_files:
                        # Pick the most recently modified database files
                        candidate_paths = sorted(list(found_files), key=os.path.getmtime, reverse=True)[:10]
                else:
                    candidate_paths = [db_path]
                
                query = self.config.get("sqlite_query", "")
                success = False
                last_error = None

                for current_db_path in candidate_paths:
                    # Skip 0-byte or inaccessible files early
                    if not os.path.exists(current_db_path) or os.path.getsize(current_db_path) == 0:
                        continue
                        
                    db_uri = f"file:{urllib.parse.quote(current_db_path)}?mode=ro"
                    
                    try:
                        conn = sqlite3.connect(db_uri, uri=True)
                        conn.row_factory = sqlite3.Row
                        cursor = conn.cursor()
                        
                        cursor.execute(query)
                        row = cursor.fetchone()
                        
                        if row:
                            data = dict(row)
                            cycle_number = data.get("cycle_number", data.get("cycle", 0))
                            cycle_time = data.get("cycle_time", 0.0)
                            total_time = data.get("total_time", data.get("time", 0.0))
                            current = data.get("current", data.get("i", 0.0))
                            
                            self.update_callback({
                                "cycle_number": cycle_number,
                                "cycle_time": cycle_time,
                                "total_time": total_time,
                                "current": current,
                                "db_path": current_db_path
                            })
                        
                        conn.close()
                        success = True
                        break # Found valid DB and updated successfully
                    except sqlite3.OperationalError as e:
                        last_error = f"SQLite Operational Error: {e} ({os.path.basename(current_db_path)})"
                        if 'conn' in locals():
                            try: conn.close()
                            except: pass
                        continue # Try next candidate file
                    except Exception as e:
                        last_error = f"SQLite Query Error: {e} ({os.path.basename(current_db_path)})"
                        if 'conn' in locals():
                            try: conn.close()
                            except: pass
                        continue

                if not success and last_error:
                    self.error_callback(f"{last_error}. Is an experiment actively running?")

            except Exception as e:
                self.error_callback(f"Monitor Thread Error: {e}")

            # Wait before next poll
            time.sleep(self.config.get("poll_interval_seconds", 1.0))
