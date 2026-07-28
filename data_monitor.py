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
        self.last_line_count = 0
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

                # Read the ENTIRE file every poll and track by line count.
                # This avoids Windows file-caching / byte-seek issues entirely.
                with open(text_file_path, 'r') as f:
                    all_lines = f.readlines()
                
                total_lines = len(all_lines)
                
                # Detect file reset (file was overwritten / has fewer lines)
                if total_lines < self.last_line_count:
                    self.last_line_count = 0
                    self.cycle_number = 0
                    self.last_index = 0
                    self.latest_data = {
                        "cycle_number": 0,
                        "cycle_time": 0.0,
                        "total_time": 0.0,
                        "current": 0.0,
                        "index": 0
                    }
                
                # Only process lines we haven't seen before
                new_lines = all_lines[self.last_line_count:]
                self.last_line_count = total_lines
                
                data_updated = False
                
                for line in new_lines:
                    parts = line.strip().split()
                    # Nova Autolab uses tabs or spaces,
                    # split() handles any whitespace sequence.
                    if len(parts) >= 3:
                        try:
                            # Try parsing the first column as a number (Index)
                            index_val = int(float(parts[0]))
                            time_val = float(parts[1])
                            current_val = float(parts[-1])  # Last column = current
                            
                            # If index drops to 1 after being > 1, it's a new cycle
                            if index_val == 1 and self.last_index > 1:
                                self.cycle_number += 1
                            elif self.cycle_number == 0 and index_val > 0:
                                self.cycle_number = 1
                                
                            self.last_index = index_val
                            
                            self.latest_data = {
                                "cycle_number": self.cycle_number,
                                "cycle_time": time_val,
                                "total_time": time_val,
                                "current": current_val,
                                "index": index_val
                            }
                            
                            data_updated = True
                            
                        except ValueError:
                            # Header row or empty row, just skip
                            pass

                if data_updated:
                    self.update_callback(self.latest_data.copy())

            except Exception as e:
                self.error_callback(f"Monitor Thread Error: {e}")

            # Wait before next poll
            time.sleep(self.config.get("poll_interval_seconds", 1.0))
