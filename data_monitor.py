import threading
import time
import json
import os

class NovaDataMonitor(threading.Thread):
    def __init__(self, config_path, update_callback, error_callback):
        super().__init__()
        self.daemon = True
        self.config_path = config_path
        self.update_callback = update_callback
        self.error_callback = error_callback
        
        self.running = True
        self.last_position = 0
        self.cycle_number = 0
        self.last_index = 0
        
        self.latest_data = {
            "cycle_number": 0,
            "cycle_time": 0.0,
            "total_time": 0.0,
            "current": 0.0,
            "index": 0
        }
        
        # Load initial config
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            self.error_callback(f"Failed to load config: {e}")
            self.config = {
                "text_file_path": "Data_sample1",
                "poll_interval_seconds": 1.0
            }

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                self._load_config()
                text_file_path = self.config.get("text_file_path", "")
                
                if not os.path.exists(text_file_path):
                    self.error_callback(f"File not found: {text_file_path}")
                    time.sleep(self.config.get("poll_interval_seconds", 1.0))
                    continue

                current_size = os.path.getsize(text_file_path)
                if current_size < self.last_position:
                    # File was truncated/restarted
                    self.last_position = 0
                    self.cycle_number = 0
                    self.last_index = 0
                    self.latest_data = {
                        "cycle_number": 0,
                        "cycle_time": 0.0,
                        "total_time": 0.0,
                        "current": 0.0,
                        "index": 0
                    }

                if current_size > self.last_position:
                    with open(text_file_path, 'r') as f:
                        f.seek(self.last_position)
                        lines = f.readlines()
                        self.last_position = f.tell()
                        
                        data_updated = False
                        
                        for line in lines:
                            parts = line.strip().split()
                            # Nova Autolab sometimes uses multiple spaces or tabs,
                            # split() handles any whitespace sequence.
                            if len(parts) >= 3:
                                try:
                                    # Try parsing the first column as an integer (Index)
                                    index_val_float = float(parts[0])
                                    index_val = int(index_val_float)
                                    time_val = float(parts[1])
                                    current_val = float(parts[-1]) # Use last column for current
                                    
                                    # If index drops to 1 after being > 1, it's a new cycle
                                    if index_val == 1 and self.last_index > 1:
                                        self.cycle_number += 1
                                    elif self.cycle_number == 0 and index_val > 0:
                                        self.cycle_number = 1
                                        
                                    self.last_index = index_val
                                    
                                    self.latest_data["cycle_number"] = self.cycle_number
                                    self.latest_data["cycle_time"] = time_val  # Assuming time starts near 0 each cycle, if not, could use a relative calculation
                                    self.latest_data["total_time"] = time_val  # Note: if time resets, total_time needs accumulation. We'll pass raw for now.
                                    self.latest_data["current"] = current_val
                                    self.latest_data["index"] = index_val
                                    
                                    data_updated = True
                                    
                                except ValueError:
                                    # Header row or empty row, just skip
                                    pass

                        if data_updated:
                            self.update_callback(self.latest_data)

            except Exception as e:
                self.error_callback(f"Monitor Thread Error: {e}")

            # Wait before next poll
            time.sleep(self.config.get("poll_interval_seconds", 1.0))
