"""
Mock SDK Monitor — Simulates the NovaSDKMonitor interface for testing
the popup logger without requiring the physical Autolab instrument or
the SDK DLL.

Generates synthetic electrochemical data (current, time, cycles) that
mimics a chronoamperometry experiment.
"""

import threading
import time
import random
import math
import json
import os
import queue


class MockSDKMonitor(threading.Thread):
    """
    Drop-in replacement for NovaSDKMonitor that generates fake
    instrument data. Same callback interface so main.py works
    identically in test mode.
    """

    def __init__(self, config_path, update_callback, error_callback):
        super().__init__()
        self.daemon = True
        self.config_path = config_path
        self.update_callback = update_callback
        self.error_callback = error_callback

        self.running = True
        self.status_queue = queue.Queue()

        # Load config for timing params
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception:
            self.config = {}

        self.poll_rate_hz = self.config.get("sdk_poll_rate_hz", 5)
        self.poll_interval = 1.0 / max(self.poll_rate_hz, 1)

    def stop(self):
        self.running = False

    def enumerate_signals(self):
        """Return simulated signal list."""
        return [
            "WE(1).Current",
            "WE(1).Potential",
            "Time",
            "Cycle",
            "Scan",
        ]

    def run(self):
        """Generate synthetic CA data — one cycle every ~60s."""
        self.status_queue.put(
            {"msg": "[MOCK] SDK connected (simulated)", "level": "info"}
        )
        self.status_queue.put(
            {"msg": "[MOCK] Procedure loaded (simulated)", "level": "info"}
        )
        self.status_queue.put(
            {
                "msg": f"[MOCK] Signals: {', '.join(self.enumerate_signals())}",
                "level": "info",
            }
        )
        self.status_queue.put(
            {"msg": "[MOCK] Streaming live data...", "level": "info"}
        )

        cycle_duration = 60.0  # seconds per cycle
        cycle_number = 1
        start_time = time.time()
        cycle_start = start_time

        while self.running:
            now = time.time()
            total_time = now - start_time
            cycle_time = now - cycle_start

            # Cycle boundary
            if cycle_time >= cycle_duration:
                cycle_number += 1
                cycle_start = now
                cycle_time = 0.0

            # Simulate chronoamperometry current decay:
            # i(t) = A * t^(-0.5) + baseline + noise
            t_safe = max(cycle_time, 0.1)
            base_current = 1e-6 * (1.0 / math.sqrt(t_safe))
            drift = 1e-8 * cycle_number  # slow drift per cycle
            noise = random.gauss(0, 5e-9)
            current = base_current + drift + noise

            data = {
                "current": current,
                "total_time": total_time,
                "cycle_time": cycle_time,
                "cycle_number": cycle_number,
                "db_path": "mock_sdk_live",
            }

            self.update_callback(data)
            time.sleep(self.poll_interval)
