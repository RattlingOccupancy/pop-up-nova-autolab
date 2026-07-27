"""
Nova SDK Monitor — Attaches to a running NOVA 2.1 experiment and streams
real-time electrochemical data (Current, Time, Cycle) into the popup logger.

Uses pythonnet (clr) to load the Autolab SDK assembly and connect to the
instrument in NOVA-managed (attached) mode, meaning the NOVA UI controls the
experiment while this script reads the live signal values.
"""

import threading
import time
import json
import os
import queue


class NovaSDKMonitor(threading.Thread):
    """
    Connects to the Autolab instrument via the Autolab SDK DLL,
    attaches to the running procedure, and polls live signals.

    Interface-compatible with NovaDataMonitor so main.py can swap
    between sqlite and sdk modes transparently.
    """

    def __init__(self, config_path, update_callback, error_callback):
        super().__init__()
        self.daemon = True
        self.config_path = config_path
        self.update_callback = update_callback
        self.error_callback = error_callback

        self.running = True
        self._connected = False
        self._instrument = None
        self._procedure = None
        self._sdk_module = None

        # Thread-safe status queue for UI
        self.status_queue = queue.Queue()

        # Load config
        self._load_config()

    # ------------------------------------------------------------------ config
    def _load_config(self):
        try:
            with open(self.config_path, "r") as f:
                self.config = json.load(f)
        except Exception as e:
            self.error_callback(f"Failed to load config: {e}")
            self.config = {}

        self.sdk_dll_path = self.config.get(
            "sdk_dll_path",
            r"C:\Program Files\Metrohm Autolab\Autolab SDK 2.1\EcoChemie.Autolab.Sdk",
        )
        self.hardware_setup_file = self.config.get("hardware_setup_file", "")
        self.nox_procedure_path = self.config.get("nox_procedure_path", "")
        self.current_signal_name = self.config.get(
            "current_signal_name", "WE(1).Current"
        )
        self.time_signal_name = self.config.get("time_signal_name", "Time")
        self.poll_rate_hz = self.config.get("sdk_poll_rate_hz", 5)
        self.poll_interval = 1.0 / max(self.poll_rate_hz, 1)

    # -------------------------------------------------------------- lifecycle
    def stop(self):
        self.running = False
        self._disconnect()

    def _push_status(self, msg, level="info"):
        """Push a status message for the GUI to pick up."""
        self.status_queue.put({"msg": msg, "level": level})

    # ------------------------------------------------------------ SDK loading
    def _load_sdk(self):
        """Load the Autolab SDK assembly via pythonnet."""
        try:
            import clr  # pythonnet

            # Add reference to the SDK DLL (without .dll extension)
            dll_path = self.sdk_dll_path
            if dll_path.lower().endswith(".dll"):
                dll_path = dll_path[:-4]

            clr.AddReference(dll_path)

            from EcoChemie.Autolab import Sdk as AutolabSDK

            self._sdk_module = AutolabSDK
            self._push_status("SDK assembly loaded successfully")
            return True
        except ImportError:
            self.error_callback(
                "pythonnet is not installed. Run: pip install pythonnet"
            )
            self._push_status("pythonnet not installed", "error")
            return False
        except FileNotFoundError:
            self.error_callback(
                f"SDK DLL not found at: {self.sdk_dll_path}\n"
                "Check the 'sdk_dll_path' in config.json"
            )
            self._push_status("SDK DLL not found", "error")
            return False
        except Exception as e:
            self.error_callback(f"Failed to load SDK assembly: {e}")
            self._push_status(f"SDK load error: {e}", "error")
            return False

    # ----------------------------------------------------------- connect flow
    def _connect(self):
        """
        Connect to the Autolab instrument in NOVA-managed / attached mode.
        The NOVA UI must already be running and controlling the instrument.
        """
        if self._sdk_module is None:
            if not self._load_sdk():
                return False

        try:
            SDK = self._sdk_module
            self._instrument = SDK.Instrument()

            # --- THE MAGIC SEQUENCE FOR NOVA-MANAGED MODE ---
            # To avoid a "Value cannot be null" error in Path.Combine, we must
            # first set EmbeddedExeFileToStart to the valid Adk.x path so the SDK
            # internally caches the directory.
            # Then we set HardwareSetupFile.
            # Then we set EmbeddedExeFileToStart back to None so it attaches to
            # the running NOVA instead of claiming the WinUSB device directly.
            
            adk_path = r"C:\Program Files\Metrohm Autolab\Autolab SDK 2.1\Hardware Setup Files\Adk.x"
            if self.config.get("sdk_dll_path"):
                base_sdk = os.path.dirname(self.config["sdk_dll_path"])
                test_path = os.path.join(base_sdk, "Hardware Setup Files", "Adk.x")
                if os.path.exists(test_path):
                    adk_path = test_path

            # Step 1: Set to valid path
            try:
                self._instrument.AutolabConnectionSettings.EmbeddedExeFileToStart = adk_path
            except AttributeError:
                pass
            try:
                self._instrument.AutolabConnection.EmbeddedExeFileToStart = adk_path
            except AttributeError:
                pass

            # Hardware setup (required even in attached mode)
            if self.hardware_setup_file:
                if not os.path.exists(self.hardware_setup_file):
                    raise ValueError(f"Hardware setup file NOT FOUND on disk: {self.hardware_setup_file}")
                self._instrument.HardwareSetupFile = self.hardware_setup_file
            else:
                # Try to auto-detect common paths
                common_paths = [
                    r"C:\ProgramData\Metrohm Autolab\12345\HardwareSetup.xml",
                    r"C:\ProgramData\Metrohm Autolab\HardwareSetup.xml",
                ]
                found = False
                for p in common_paths:
                    if os.path.exists(p):
                        self._instrument.HardwareSetupFile = p
                        self._push_status(f"Auto-detected hardware setup: {p}")
                        found = True
                        break
                if not found:
                    raise ValueError("No HardwareSetupFile configured in config.json, and auto-detect failed.")

            # Connect
            
            # Step 3: Set back to None for NOVA-managed (Attached) mode
            try:
                self._instrument.AutolabConnectionSettings.EmbeddedExeFileToStart = None
            except AttributeError:
                pass
            try:
                self._instrument.AutolabConnection.EmbeddedExeFileToStart = None
            except AttributeError:
                pass
                
            self._instrument.Connect()
            self._connected = True
            self._push_status("Connected to Autolab instrument")
            return True

        except Exception as e:
            self._connected = False
            err = str(e)
            if "already connected" in err.lower() or "in use" in err.lower():
                self.error_callback(
                    "Cannot connect — NOVA UI or another SDK instance is "
                    "already using the instrument. Close NOVA's measurement "
                    "window or set up NOVA-managed mode."
                )
            else:
                self.error_callback(f"SDK connection failed: {e}")
            self._push_status(f"Connection failed: {e}", "error")
            return False

    def _disconnect(self):
        """Gracefully disconnect from the instrument."""
        try:
            if self._instrument is not None and self._connected:
                self._instrument.Disconnect()
                self._push_status("Disconnected from instrument")
        except Exception as e:
            self._push_status(f"Disconnect warning: {e}", "warning")
        finally:
            self._connected = False
            self._instrument = None
            self._procedure = None

    # --------------------------------------------------------- procedure load
    def _load_procedure(self):
        """
        Load the .nox procedure file.  If nox_procedure_path is empty or the
        file does not exist, the monitor will try to read signals directly
        from the instrument's active measurement.
        """
        if not self.nox_procedure_path:
            self._push_status(
                "No .nox procedure configured — will poll instrument directly"
            )
            return True  # proceed without a procedure

        if not os.path.exists(self.nox_procedure_path):
            self.error_callback(
                f"Procedure file not found: {self.nox_procedure_path}"
            )
            self._push_status("Procedure file not found", "error")
            return False

        try:
            self._procedure = self._instrument.LoadProcedure(
                self.nox_procedure_path
            )
            self._push_status(
                f"Procedure loaded: {os.path.basename(self.nox_procedure_path)}"
            )
            return True
        except Exception as e:
            self.error_callback(f"Failed to load procedure: {e}")
            self._push_status(f"Procedure load error: {e}", "error")
            return False

    # ---------------------------------------------------------- signal reader
    def _read_signals(self):
        """
        Read the live signal values from the active procedure / instrument.
        Returns a dict with: current, total_time, cycle_time, cycle_number.
        """
        data = {
            "current": 0.0,
            "total_time": 0.0,
            "cycle_time": 0.0,
            "cycle_number": 0,
            "db_path": "autolab_sdk_live",
        }

        try:
            source = self._procedure if self._procedure else self._instrument

            # Read current signal
            try:
                current_sig = source.get_Signal(self.current_signal_name)
                if current_sig is not None:
                    data["current"] = float(current_sig.Value)
            except Exception:
                # Try alternate signal names
                for alt in ["WE(1).Current", "i", "Current", "WE.Current"]:
                    try:
                        sig = source.get_Signal(alt)
                        if sig is not None:
                            data["current"] = float(sig.Value)
                            break
                    except Exception:
                        continue

            # Read time signal
            try:
                time_sig = source.get_Signal(self.time_signal_name)
                if time_sig is not None:
                    data["total_time"] = float(time_sig.Value)
                    data["cycle_time"] = float(time_sig.Value)
            except Exception:
                for alt in ["Time", "t", "Elapsed Time"]:
                    try:
                        sig = source.get_Signal(alt)
                        if sig is not None:
                            data["total_time"] = float(sig.Value)
                            data["cycle_time"] = float(sig.Value)
                            break
                    except Exception:
                        continue

            # Read cycle number (if available)
            try:
                # Try common cycle-related signal/parameter names
                for cycle_name in ["Cycle", "Scan", "CurrentCycle"]:
                    try:
                        sig = source.get_Signal(cycle_name)
                        if sig is not None:
                            data["cycle_number"] = int(sig.Value)
                            break
                    except Exception:
                        continue
            except Exception:
                pass

            # Attempt to derive cycle_time from commands if procedure is loaded
            if self._procedure is not None:
                try:
                    commands = self._procedure.Commands
                    for cmd_name in ["FHLevel1", "FHLevel", "CVLinearScanAdc164"]:
                        try:
                            cmd = commands[cmd_name]
                            params = cmd.CommandParameters
                            # Look for cycle-related params
                            try:
                                cycle_val = params["CurrentCycle"]
                                data["cycle_number"] = int(cycle_val.Value)
                            except Exception:
                                pass
                            break
                        except Exception:
                            continue
                except Exception:
                    pass

        except Exception as e:
            raise RuntimeError(f"Signal read error: {e}")

        return data

    def enumerate_signals(self):
        """
        Return a list of all available signal names from the active
        procedure. Useful for the user to discover valid signal names.
        """
        signals = []
        try:
            source = self._procedure if self._procedure else self._instrument
            if source is not None and hasattr(source, "Signals"):
                sig_collection = source.Signals
                for i in range(sig_collection.Count):
                    sig = sig_collection[i]
                    signals.append(sig.Name)
        except Exception as e:
            self._push_status(f"Could not enumerate signals: {e}", "warning")
        return signals

    # --------------------------------------------------------------- main loop
    def run(self):
        """Main thread loop: connect → load procedure → poll signals."""

        # Step 1: Connect
        self._push_status("Connecting to Autolab instrument...")
        if not self._connect():
            # Retry loop with backoff
            retry_count = 0
            while self.running and not self._connected:
                retry_count += 1
                wait = min(retry_count * 5, 30)  # 5s, 10s, 15s, ... max 30s
                self._push_status(
                    f"Retrying connection in {wait}s... (attempt {retry_count})"
                )
                time.sleep(wait)
                if not self.running:
                    return
                self._load_config()  # re-read config in case user updated paths
                self._connect()

        if not self.running:
            return

        # Step 2: Load procedure (if configured)
        self._load_procedure()

        # Step 3: Enumerate available signals (for debug/info)
        available_signals = self.enumerate_signals()
        if available_signals:
            self._push_status(
                f"Available signals: {', '.join(available_signals)}"
            )

        # Step 4: Poll loop
        self._push_status("Streaming live data...")
        consecutive_errors = 0

        while self.running:
            try:
                data = self._read_signals()
                self.update_callback(data)
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                if consecutive_errors <= 3:
                    self.error_callback(f"Signal read error: {e}")
                elif consecutive_errors == 10:
                    self.error_callback(
                        "Persistent signal errors — is the experiment still running?"
                    )
                    self._push_status("Signal errors — check NOVA", "error")
                # Don't flood the error callback
                if consecutive_errors > 50:
                    self._push_status(
                        "Too many errors, attempting reconnect...", "error"
                    )
                    self._disconnect()
                    time.sleep(5)
                    if self.running:
                        self._connect()
                        self._load_procedure()
                        consecutive_errors = 0

            time.sleep(self.poll_interval)
