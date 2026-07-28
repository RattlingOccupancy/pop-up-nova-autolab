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

        # Load config once at startup (no per-poll reload)
        self._load_config()

    def _load_config(self):
        try:
            with open(self.config_path, 'r') as f:
                self.config = json.load(f)
        except Exception as e:
            self.error_callback(f"Failed to load config: {e}")
            self.config = {
                "text_file_path": "Data_sample1",
                "poll_interval_seconds": 0.25
            }

    def stop(self):
        self.running = False

    def count_cycles_fast(self, file_path):
        """Counts cycles in the file extremely quickly by scanning binary contents."""
        cycle_count = 0
        try:
            with open(file_path, 'rb') as f:
                # Check if first character is '1' (no headers case)
                first_char = f.read(1)
                if first_char == b'1':
                    cycle_count += 1
                f.seek(0)

                chunk_size = 1024 * 1024
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    # Index 1 lines start with newline + '1' + separator
                    cycle_count += chunk.count(b'\n1\t') + chunk.count(b'\n1 ')
        except Exception as e:
            print(f"Error counting cycles: {e}")
        return max(1, cycle_count)

    def get_last_line_data(self, file_path):
        """Reads only the end of the file to populate the UI instantly on startup."""
        try:
            size = os.path.getsize(file_path)
            if size == 0:
                return None
            with open(file_path, 'rb') as f:
                # Read last 4KB
                seek_pos = max(0, size - 4096)
                f.seek(seek_pos)
                content = f.read().decode('utf-8', errors='ignore')
                lines = content.splitlines()
                # Find the last valid data line
                for line in reversed(lines):
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            index_val = int(float(parts[0]))
                            time_val = float(parts[1])
                            current_val = float(parts[-1])
                            return {
                                "index": index_val,
                                "time": time_val,
                                "current": current_val
                            }
                        except ValueError:
                            continue
        except Exception as e:
            print(f"Error reading last line: {e}")
        return None

    def _read_new_complete_lines(self, file_path):
        """
        Re-opens the file each poll to bypass OS file stat caching.
        Only reads COMPLETE lines (ending with newline) so partial writes
        by Nova are not consumed prematurely.
        Returns a list of complete line strings.
        """
        try:
            # Re-open each time — this forces the OS to see the latest
            # file size and contents, even if another process (Nova) is
            # actively writing with buffered I/O.
            with open(file_path, 'rb') as f:
                f.seek(0, 2)  # seek to end
                current_size = f.tell()

                if current_size < self.last_position:
                    # File was truncated / replaced — reset
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

                if current_size <= self.last_position:
                    return []

                f.seek(self.last_position)
                raw = f.read(current_size - self.last_position)

            text = raw.decode('utf-8', errors='ignore')

            # Only consume up to the last complete line (ending with \n).
            # If Nova is mid-write, the trailing partial line stays for
            # the next poll.
            last_newline = text.rfind('\n')
            if last_newline == -1:
                # No complete line yet — don't advance position
                return []

            complete_text = text[:last_newline + 1]
            # Advance position only by the bytes of complete lines
            self.last_position += len(complete_text.encode('utf-8'))

            lines = complete_text.splitlines()
            return lines

        except FileNotFoundError:
            return []
        except Exception as e:
            self.error_callback(f"Read error: {e}")
            return []

    def run(self):
        # Startup phase: quickly initialize state from existing file
        text_file_path = self.config.get("text_file_path", "")
        poll_interval = self.config.get("poll_interval_seconds", 0.25)

        if os.path.exists(text_file_path):
            try:
                current_size = os.path.getsize(text_file_path)
                self.last_position = current_size

                self.cycle_number = self.count_cycles_fast(text_file_path)
                last_data = self.get_last_line_data(text_file_path)
                if last_data:
                    self.last_index = last_data["index"]
                    self.latest_data = {
                        "cycle_number": self.cycle_number,
                        "cycle_time": last_data["time"],
                        "total_time": last_data["time"],
                        "current": last_data["current"],
                        "index": last_data["index"]
                    }
                    self.update_callback(self.latest_data.copy())
            except Exception as e:
                self.error_callback(f"Error initializing monitor: {e}")

        # Polling phase: only read new complete lines appended to the file
        while self.running:
            try:
                if not os.path.exists(text_file_path):
                    self.error_callback(f"File not found: {text_file_path}")
                    time.sleep(poll_interval)
                    continue

                new_lines = self._read_new_complete_lines(text_file_path)

                data_updated = False
                for line in new_lines:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            index_val = int(float(parts[0]))
                            time_val = float(parts[1])
                            current_val = float(parts[-1])

                            # Detect new cycle start
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
                            pass

                if data_updated:
                    self.update_callback(self.latest_data.copy())

            except Exception as e:
                self.error_callback(f"Monitor Thread Error: {e}")

            time.sleep(poll_interval)
