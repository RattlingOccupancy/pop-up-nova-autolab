import tkinter as tk
from tkinter import ttk, messagebox
import json
import time
from datetime import datetime
import os
import sys

from data_monitor import NovaDataMonitor

class NovaLoggerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Nova Autolab Logger")
        
        # Always on top
        self.root.attributes('-topmost', True)
        
        # Make the window non-resizable to keep it compact
        self.root.resizable(False, False)
        
        # Determine paths
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = os.path.join(self.base_dir, "config.json")
        
        # Load config
        self._load_config()
        
        # Initialize Logger (Excel removed)
        
        # Latest data state
        self.latest_data = {
            "cycle_number": 0,
            "cycle_time": 0.0,
            "total_time": 0.0,
            "current": 0.0,
            "index": 0
        }
        
        self.active_glucose = str(self.config.get("default_starting_glucose", "0"))
        self.log_on_index = int(self.config.get("log_on_index", 30))
        self._last_cycle_logged = -1
        
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
                "text_file_path": "Data_sample1",
                "preset_glucose_values": ["0", "25", "50", "75", "100", "150", "200"],
                "poll_interval_seconds": 1.0,
                "log_on_index": 30,
                "default_starting_glucose": "0"
            }

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

        ttk.Label(data_frame, text="Index:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.lbl_index = ttk.Label(data_frame, text="0")
        self.lbl_index.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

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
        
        # Just update status
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._update_status(f"Manually set {self.active_glucose} at {timestamp.split(' ')[1]}", "green")


    def _update_status(self, msg, color):
        self.lbl_status.config(text=msg, foreground=color)
        # Clear status after 3 seconds
        self.root.after(3000, lambda: self.lbl_status.config(text="Monitoring...", foreground="black"))

    def _on_data_update(self, data):
        # Update thread-safe way in tkinter
        self.root.after(0, self._update_ui_with_data, data)

    def _update_ui_with_data(self, data):
        self.latest_data = data
        self.lbl_current.config(text=f"{data.get('current', 0.0):.6e}")
        self.lbl_cycle_num.config(text=f"{data.get('cycle_number', 0)}")
        self.lbl_index.config(text=f"{data.get('index', 0)}")
        self.lbl_total_time.config(text=f"{data.get('total_time', 0.0):.2f}")

        # Check if we should log based on index (Auto-logging removed)
        current_index = data.get("index", 0)
        current_cycle = data.get("cycle_number", 0)
        
        if current_index == self.log_on_index and self._last_cycle_logged != current_cycle:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self._update_status(f"Auto-reached index {self.log_on_index} at {timestamp.split(' ')[1]}", "green")
            self._last_cycle_logged = current_cycle

    def _on_monitor_error(self, err_msg):
        self.root.after(0, lambda: self._update_status(err_msg[:40], "red"))
        print(err_msg)
        
    def on_closing(self):
        self.monitor.stop()
        self.root.destroy()

if __name__ == "__main__":
    root = tk.Tk()
    app = NovaLoggerApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
