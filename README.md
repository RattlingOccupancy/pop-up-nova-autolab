# Nova Potentiostat Floating Logger

A lightweight, always-on-top Windows desktop assistant designed to log glucose additions during long Step Chronoamperometry experiments. It fetches electrochemical measurements (Current, Cycle, Time) in real-time and logs them to an Excel file with one click.

**Supports two data acquisition modes:**
- **SDK Mode** (recommended) — Connects directly to the Autolab instrument via the NOVA Autolab SDK, reading live signals from the running experiment in real-time.
- **SQLite Mode** (fallback) — Polls the NOVA 2.1 SQLite database files for the latest data point.

---

## 1. Initial Setup (First-Time Only)

### Install Python
1. Download Python 3.12+ from [python.org/downloads](https://www.python.org/downloads/).
2. **CRITICAL STEP**: When running the installer, you must check the box at the bottom that says **"Add python.exe to PATH"**.
3. Install and verify by opening Command Prompt and typing `python --version`.

### Install Dependencies
1. Open Command Prompt and navigate to this folder:
   ```cmd
   cd C:\Users\shanu\Desktop\bodyloop_tool\pop-up-nova-autolab
   ```
2. Install the required Python packages:
   ```cmd
   pip install -r requirements.txt
   ```
   This installs `openpyxl`, `pandas`, `pyodbc`, and **`pythonnet`** (required for SDK mode).

---

## 2. How to Run with Mock Data (Testing Mode)

Before connecting to the real equipment, you can test the logger with simulated data.

### Test SDK Mode (Recommended)
Double-click `run_test_sdk.bat`, OR run:
```cmd
python run_test.py sdk
```
This launches the logger with a **MockSDKMonitor** that generates realistic chronoamperometry data (Cottrell-style current decay) without any hardware. You can click glucose buttons and see data flowing.

### Test SQLite Mode
Double-click `run_test.bat`, OR run:
```cmd
python run_test.py
```
This launches a dummy SQLite database writer (`mock_db.py`) and the logger in SQLite polling mode.

---

## 3. How to Run with Real NOVA 2.1 Equipment (SDK Mode)

This is the primary mode. The logger attaches to the running NOVA 2.1 experiment and reads live signals directly via the Autolab SDK.

### Prerequisites
1. **NOVA 2.1** must be installed with the **Autolab SDK 2.1**.
2. The SDK version must match your NOVA version (both 2.1.x).
3. `pythonnet` must be installed (`pip install pythonnet`).

### Step-by-Step

1. **Start your experiment in NOVA 2.1** — the instrument must be connected and a measurement procedure must be running.

2. **Verify your `config.json` settings:**
   ```json
   {
       "data_source": "sdk",
       "sdk_dll_path": "C:\\Program Files\\Metrohm Autolab\\Autolab SDK 2.1\\EcoChemie.Autolab.Sdk",
       "hardware_setup_file": "C:\\ProgramData\\Metrohm Autolab\\12345\\HardwareSetup.xml",
       "nox_procedure_path": "",
       "current_signal_name": "WE(1).Current",
       "time_signal_name": "Time",
       "sdk_poll_rate_hz": 5
   }
   ```
   - `sdk_dll_path` — Path to the SDK DLL (without `.dll` extension). Find it in your Autolab SDK installation folder.
   - `hardware_setup_file` — Path to your instrument's `HardwareSetup.xml`. See Section 5 below to find this.
   - `nox_procedure_path` — (Optional) Path to a `.nox` procedure file. Leave empty if the procedure is already running in NOVA.
   - `current_signal_name` / `time_signal_name` — The signal names to read. See Section 6 to discover yours.

3. **Launch the logger:**
   ```cmd
   python main.py
   ```
   Or double-click `run_app.bat`.

4. The popup will show:
   - **Connection status** at the top (Connecting → Connected → Streaming live data)
   - **Live values** for Current, Cycle, Time
   - **Glucose buttons** and manual entry for logging

---

## 4. How to Run with Real NOVA 2.1 Equipment (SQLite Fallback)

If the SDK approach doesn't work for your setup, you can fall back to SQLite database polling:

1. Change `config.json`:
   ```json
   {
       "data_source": "sqlite",
       "sqlite_db_path": "C:\\Users\\Public\\Documents\\Metrohm Autolab\\NOVA 2.1\\Database"
   }
   ```

2. Start your experiment in NOVA 2.1.

3. Launch the logger:
   ```cmd
   python main.py
   ```

4. See Section 7 for finding the database path and adjusting the SQL query.

---

## 5. Finding Your SDK & Hardware Setup Paths

### SDK DLL Path
1. Open File Explorer and navigate to: `C:\Program Files\Metrohm Autolab\`
2. Look for a folder named `Autolab SDK 2.1` (or similar version).
3. Inside, find `EcoChemie.Autolab.Sdk.dll`.
4. Copy the path **without the `.dll` extension** into `config.json` → `sdk_dll_path`.

### Hardware Setup XML
1. Navigate to: `C:\ProgramData\Metrohm Autolab\`
2. Look for a numbered subfolder (e.g., `12345\`) — this is your instrument serial number.
3. Inside, find `HardwareSetup.xml` (it may include the model name, e.g., `HardwareSetup.PGSTAT302N.xml`).
4. Copy the full path into `config.json` → `hardware_setup_file`.

**If you can't find it:**
- Open NOVA 2.1, go to **Hardware Setup** in the menu — the dialog will show the path being used.
- Alternatively, search: `dir /s /b C:\ProgramData\Metrohm*\HardwareSetup*.xml`

---

## 6. Discovering Signal Names

The exact signal names depend on your NOVA procedure. To discover them:

### Option A: Check the NOVA Procedure
1. Open your procedure in NOVA 2.1.
2. Look at the **Signal Sampler** or **Plot Axes** — the axis labels are the signal names.
3. Common names: `WE(1).Current`, `WE(1).Potential`, `Time`, `Cycle`, `Scan`.

### Option B: Let the Logger Auto-Discover
1. Connect with the SDK (run the logger).
2. The logger prints all available signals to the console when it connects.
3. Look for the line: `Available signals: WE(1).Current, Time, ...`
4. Update `config.json` with the correct names.

### Option C: Enumerate Programmatically
```python
# Quick script to list signals
import clr
clr.AddReference(r"C:\Program Files\Metrohm Autolab\Autolab SDK 2.1\EcoChemie.Autolab.Sdk")
from EcoChemie.Autolab import Sdk as AutolabSDK

instrument = AutolabSDK.Instrument()
instrument.AutolabConnectionSettings.EmbeddedExeFileToStart = None
instrument.HardwareSetupFile = r"C:\ProgramData\Metrohm Autolab\12345\HardwareSetup.xml"
instrument.Connect()

proc = instrument.LoadProcedure(r"C:\path\to\your\procedure.nox")
for i in range(proc.Signals.Count):
    print(proc.Signals[i].Name)

instrument.Disconnect()
```

---

## 7. SQLite Mode — Finding the Data Path & Configuring

### A. Locate the Database Path
By default, NOVA 2.1 writes its active measurement databases to public documents. 
1. The default path (pre-filled in `config.json`) is usually:
   `C:\Users\Public\Documents\Metrohm Autolab\NOVA 2.1\Database`
2. **If you can't find it:** 
   - Start an experiment in NOVA.
   - Open Windows **Resource Monitor** (Press `Win + R`, type `resmon`, hit Enter).
   - Go to the **Disk** tab.
   - Look for the `Nova` process under "Disk Activity" and look at the "File" column to see exactly where it is writing `.sqlite` or `.nox` files.
   - Update the `"sqlite_db_path"` in `config.json` with this exact folder or file path.

### B. Adjust the SQL Query (`config.json`)
1. Make sure NOVA has generated at least one database file.
2. Run the included inspection tool:
   ```cmd
   python inspect_db.py
   ```
3. This tool will connect to the NOVA database and print out all the Table Names and Column Names.
4. Look for the table that contains `Time`, `Current`, and `Cycle` (or `Step`).
5. Open `config.json` and modify the `"sqlite_query"` to SELECT those specific columns.

---

## 8. config.json — Full Reference

| Field | Mode | Description |
|---|---|---|
| `data_source` | Both | `"sdk"` or `"sqlite"` — which acquisition method to use |
| `sdk_dll_path` | SDK | Path to `EcoChemie.Autolab.Sdk` (no `.dll` extension) |
| `hardware_setup_file` | SDK | Path to `HardwareSetup.xml` for your PGSTAT |
| `nox_procedure_path` | SDK | Optional `.nox` procedure file path |
| `current_signal_name` | SDK | Signal name for current (default: `WE(1).Current`) |
| `time_signal_name` | SDK | Signal name for time (default: `Time`) |
| `sdk_poll_rate_hz` | SDK | How often to read signals (default: 5 Hz) |
| `sqlite_db_path` | SQLite | Path to NOVA's database directory or file |
| `sqlite_query` | SQLite | SQL query to extract the latest data point |
| `poll_interval_seconds` | SQLite | Polling interval in seconds |
| `excel_output_path` | Both | Output Excel file name |
| `preset_glucose_values` | Both | Quick-buttons for glucose concentrations |
| `trigger_cycle_time_seconds` | Both | Cycle time at which auto-logging fires |
| `default_starting_glucose` | Both | Initial glucose concentration label |
| `record_cycles` | Both | Number of cycles to record before skipping |
| `skip_cycles` | Both | Number of cycles to skip after recording |

---

## 9. Troubleshooting

### SDK Mode Issues

| Problem | Solution |
|---|---|
| `pythonnet is not installed` | Run `pip install pythonnet` |
| `SDK DLL not found` | Check `sdk_dll_path` in `config.json` — must point to actual DLL location |
| `Connection failed` | Ensure NOVA 2.1 is running, instrument is connected, and no other SDK app is attached |
| `Signal read error` | Verify signal names with Section 6 — they must match your procedure |
| `NOVA UI conflict` | NOVA interactive UI and SDK cannot both control the instrument — use attached/managed mode |

### SQLite Mode Issues

| Problem | Solution |
|---|---|
| `Database Locked` | NOVA may lock the DB exclusively — try SDK mode or use NOVA's "Export ASCII data" command |
| `No SQLite files found` | Check `sqlite_db_path` — use Resource Monitor to find where NOVA writes |
| `.nox` files only | `.nox` files are zipped — use the `Database` folder for live `.sqlite` files |

---

## 10. File Structure

```
pop-up-nova-autolab/
├── main.py              # Main GUI application (supports SDK + SQLite modes)
├── nova_sdk_monitor.py  # SDK-based real-time data acquisition
├── data_monitor.py      # SQLite-based data polling (fallback)
├── mock_sdk.py          # Mock SDK for testing without hardware
├── mock_db.py           # Mock SQLite database for testing
├── excel_logger.py      # Excel output logger
├── inspect_db.py        # Database inspection utility
├── config.json          # All configuration settings
├── requirements.txt     # Python dependencies
├── run_app.bat          # Launch the real logger
├── run_test.bat         # Test with mock SQLite data
├── run_test_sdk.bat     # Test with mock SDK data
└── run_test.py          # Test runner (supports both modes)
```
