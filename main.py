import tkinter as tk
from tkinter import ttk, messagebox
import json
import time
from datetime import datetime
import os
import sys

from excel_logger import ExcelLogger
from data_monitor import NovaDataMonitor

class NovaLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Glucose Logger")
        
        # Always on top
        self.root.attributes('-topmost', True)
        
        # Make the window non-resizable to keep it compact
        self.root.resizable(False, False)
        
        # Determine paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_dir, "config.json")
        
        # Load config
        self._load_config()
        
        # Initialize Logger
        self.excel_logger = ExcelLogger(os.path.join(self.base_dir, self.config.get("excel_output_path", "nova_experiment_log.xlsx")))
        
        # Latest data state
        self.latest_data = {
            "cycle_number": 0,
            "cycle_time": 0.0,
            "total_time": 0.0,
            "current": 0.0
        }
        
        self.active_glucose = str(self.config.get("default_starting_glucose", "0"))
        self.trigger_cycle_time = float(self.config.get("trigger_cycle_time_seconds", 33))
        self.record_cycles = int(self.config.get("record_cycles", 50))
        self.skip_cycles = int(self.config.get("skip_cycles", 32))
        self._last_cycle_number_logged = None   # tracks which cycle we've already fired for
        self._last_cycle_time_seen = -1.0       # tracks previous cycle_time, for crossing detection
        self._last_db_path = None
        self._last_total_time_seen = -1.0
        self.start_cycle_number = None
        
        # Build UI
        self._build_ui()
        
        # Start Data Monitor
        self.monitor = NovaDataMonitor(self.config_path, self._on_data_update, self._on_monitor_error)
        self.monitor.start()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            print(f"Error loading config: {e}")
            self.config = {
                "sqlite_db_path": "temp_nova_data.sqlite",
                "excel_output_path": "nova_experiment_log.xlsx",
                "preset_glucose_values": ["0", "25", "50", "75", "100", "150", "200"],
                "poll_interval_seconds": 1.0,
                "sqlite_query": "SELECT p.y AS current, p.t AS total_time, p.t AS cycle_time, COALESCE(m.cycle, 1) AS cycle_number FROM point p LEFT JOIN measurementpart m ON p.measurementpart_id = m.measurementpart_id ORDER BY p.point_id DESC LIMIT 1;",
                "trigger_cycle_time_seconds": 33,
                "default_starting_glucose": "0",
                "record_cycles": 50,
                "skip_cycles": 32
            }
        
        # Override config if running in test mode
        if os.environ.get("NOVA_TEST_MODE") == "1":
            self.config["sqlite_db_path"] = "temp_nova_data.sqlite"

    def _build_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # --- Data Display Section ---
        data_frame = ttk.LabelFrame(main_frame, text="Live Experiment Data", padding="5")
        data_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Current
        ttk.Label(data_frame, text="Current (A):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.lbl_current = ttk.Label(data_frame, text="0.0", font=("Arial", 10, "bold"))
        self.lbl_current.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Cycle Info
        ttk.Label(data_frame, text="Cycle Number:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.lbl_cycle_num = ttk.Label(data_frame, text="0")
        self.lbl_cycle_num.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(data_frame, text="Cycle Time (s):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.lbl_cycle_time = ttk.Label(data_frame, text="0.0")
        self.lbl_cycle_time.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(data_frame, text="Total Time (s):").grid(row=3, column=0, sticky=tk.W, padx=5, pady=2)
        self.lbl_total_time = ttk.Label(data_frame, text="0.0")
        self.lbl_total_time.grid(row=3, column=1, sticky=tk.W, padx=5, pady=2)

        # Active Glucose State
        ttk.Label(data_frame, text="Active Glucose:").grid(row=4, column=0, sticky=tk.W, padx=5, pady=2)
        self.lbl_active_glucose = ttk.Label(data_frame, text=self.active_glucose, font=("Arial", 10, "bold"), foreground="blue")
        self.lbl_active_glucose.grid(row=4, column=1, sticky=tk.W, padx=5, pady=2)

        # --- Quick Buttons Section ---
        btn_frame = ttk.LabelFrame(main_frame, text="Quick Glucose Logging", padding="5")
        btn_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        preset_values = self.config.get("preset_glucose_values", ["0", "25", "50", "75", "100", "150", "200"])
        
        # Create buttons in a grid
        cols = 4
        for idx, val in enumerate(preset_values):
            r = idx // cols
            c = idx % cols
            btn = ttk.Button(btn_frame, text=val, width=5, command=lambda v=val: self._log_glucose(v))
            btn.grid(row=r, column=c, padx=2, pady=2)

        # --- Manual Entry Section ---
        manual_frame = ttk.Frame(main_frame)
        manual_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E))
        
        ttk.Label(manual_frame, text="Manual:").pack(side=tk.LEFT, padx=(0, 5))
        self.entry_manual = ttk.Entry(manual_frame, width=10)
        self.entry_manual.pack(side=tk.LEFT, padx=(0, 5))
        self.entry_manual.bind("<Return>", lambda event: self._log_manual())
        
        btn_save = ttk.Button(manual_frame, text="Save", width=6, command=self._log_manual)
        btn_save.pack(side=tk.LEFT)
        
        # Status Label
        self.lbl_status = ttk.Label(main_frame, text="Ready.", foreground="green", font=("Arial", 8))
        self.lbl_status.grid(row=3, column=0, columnspan=2, sticky=tk.W, pady=(10, 0))

    def _log_manual(self):
        val = self.entry_manual.get().strip()
        if val:
            self._log_glucose(val)
            self.entry_manual.delete(0, tk.END)

    def _log_glucose(self, value):
        # Update state
        self.active_glucose = str(value)
        self.lbl_active_glucose.config(text=self.active_glucose)
        
        # Log immediately
        self._write_to_excel(is_auto=False)

    def _write_to_excel(self, is_auto=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        cycle_number = self.latest_data.get("cycle_number", 0)
        start_cycle = self.start_cycle_number if self.start_cycle_number is not None else 1
        relative_cycle = max(1, cycle_number - start_cycle + 1)
        
        window_size = self.record_cycles + self.skip_cycles
        if window_size > 0:
            position = (relative_cycle - 1) % window_size
            display_cycle = position + 1
        else:
            display_cycle = relative_cycle

        success = self.excel_logger.log_entry(
            timestamp=timestamp,
            cycle_number=display_cycle,
            cycle_time=self.latest_data["cycle_time"],
            total_time=self.latest_data["total_time"],
            current=self.latest_data["current"],
            glucose_concentration=self.active_glucose
        )
        
        if success:
            prefix = "Auto-logged" if is_auto else "Manually logged"
            self._update_status(f"{prefix} {self.active_glucose} at {timestamp.split(' ')[1]}", "green")
        else:
            self._update_status("Error logging to Excel!", "red")

    def _update_status(self, msg, color):
        self.lbl_status.config(text=msg, foreground=color)
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.lbl_status.config(text="Monitoring...", foreground="black"))

    def _on_data_update(self, data):
        # Update thread-safe way in tkinter
        self.root.after(0, self._update_ui_with_data, data)

    def _update_ui_with_data(self, data):
        db_path = data.get("db_path")
        total_time = data.get("total_time", 0.0)
        cycle_number = data.get("cycle_number", 0)
        cycle_time = data.get("cycle_time", 0.0)
        
        # Check for experiment reset/new experiment file/time restart
        if (self._last_db_path is not None and db_path != self._last_db_path) or (total_time < self._last_total_time_seen):
            self._last_cycle_number_logged = None
            self._last_cycle_time_seen = -1.0
            self.start_cycle_number = None
            
        self._last_db_path = db_path
        self._last_total_time_seen = total_time
        
        # Initialize start cycle number when we see the first valid cycle number
        if self.start_cycle_number is None and cycle_number > 0:
            self.start_cycle_number = cycle_number
            
        # Calculate relative cycle number
        start_cycle = self.start_cycle_number if self.start_cycle_number is not None else 1
        relative_cycle = max(1, cycle_number - start_cycle + 1)
        
        window_size = self.record_cycles + self.skip_cycles
        if window_size > 0:
            position = (relative_cycle - 1) % window_size
            display_cycle = position + 1
            is_recording_cycle = position < self.record_cycles
        else:
            display_cycle = relative_cycle
            is_recording_cycle = True

        self.latest_data = data
        self.lbl_current.config(text=f"{data.get('current', 0.0):.6e}")
        self.lbl_cycle_num.config(text=f"{display_cycle}")
        self.lbl_cycle_time.config(text=f"{cycle_time:.2f}")
        self.lbl_total_time.config(text=f"{total_time:.2f}")

        # New cycle started -> allow logging again
        if cycle_number != self._last_cycle_number_logged and cycle_time < self._last_cycle_time_seen:
            self._last_cycle_number_logged = None

        # Fire once when cycle_time crosses the threshold, per cycle
        if (self._last_cycle_time_seen < self.trigger_cycle_time <= cycle_time
                and cycle_number != self._last_cycle_number_logged):
            
            if is_recording_cycle:
                self._write_to_excel(is_auto=True)
                
            self._last_cycle_number_logged = cycle_number

        self._last_cycle_time_seen = cycle_time

    def _on_monitor_error(self, err_msg):
        self.root.after(0, lambda: self._update_status("DB Error", "red"))
        print(err_msg)
        
    def on_closing(self):
        self.monitor.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NovaLoggerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()