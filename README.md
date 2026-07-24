# Nova Potentiostat Floating Logger

A lightweight, always-on-top Windows desktop assistant designed to log glucose additions during long Step Chronoamperometry experiments. It automatically fetches electrochemical measurements (Current, Cycle, Time) from the NOVA 2.1 SQLite database in real-time and logs them to an Excel file with one click.

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

---

## 2. How to Run with the Dummy Server (Testing Mode)

Before connecting to the real equipment, you can test the logger against a simulated database.

1. Double-click the `run_test.bat` file in File Explorer, OR run this in Command Prompt:
   ```cmd
   python run_test.py
   ```
2. This will launch a dummy server (`mock_db.py`) in the background that generates fake electrochemical data and saves it to a temporary database.
3. The main Nova Logger UI will appear on top. You can click the glucose buttons and see the data being logged to `nova_experiment_log.xlsx`.
4. When you close the UI, the dummy server automatically shuts down.

---

## 3. How to Run with Real NOVA 2.1 Equipment

Once you have configured your database paths and SQL queries (see Section 4), running the real app is simple:

1. Start your experiment in NOVA 2.1.
2. Double-click the `run_app.bat` file, OR run:
   ```cmd
   python main.py
   ```
3. The logger will sit on top of your NOVA software, fetching real-time data from the configured database path.

---

## 4. Finding the Data Path & Configuring for NOVA 2.1 (Full Solution)

NOVA 2.1 handles data differently depending on your procedure settings. To get real data streaming into the logger, follow these steps:

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
The current `"sqlite_query"` in `config.json` is set up for the previous Ivium system. NOVA uses different table and column names.
1. Make sure NOVA has generated at least one database file.
2. Run the included inspection tool:
   ```cmd
   python inspect_db.py
   ```
3. This tool will connect to the NOVA database and print out all the Table Names and Column Names.
4. Look for the table that contains `Time`, `Current`, and `Cycle` (or `Step`).
5. Open `config.json` and modify the `"sqlite_query"` to SELECT those specific columns. For example:
   `"SELECT current_column AS current, time_column AS total_time, cycle_column AS cycle_number FROM nova_table ORDER BY id DESC LIMIT 1;"`

---

## 5. Caveats & Workarounds

### Caveat 1: "Database Locked" Errors
**The Problem:** NOVA 2.1 might exclusively lock its SQLite database file while an experiment is running to ensure data integrity. If this happens, our Python script won't be able to read it and will throw a "Database Locked" error.

**The Workaround (Export to ASCII):**
If the database is locked, you must modify your NOVA 2.1 procedure to export data externally.
1. Open your NOVA procedure.
2. Add the **"Export ASCII data"** command to your measurement loop.
3. Configure it to continuously write (append) the live data to a `.csv` or `.txt` file on your Desktop.
4. If you do this, the Python logger (`data_monitor.py`) will need a minor code tweak to read the last line of that `.csv` file instead of querying a database. (This is actually faster and easier than reading SQLite!).

### Caveat 2: `.nox` Files are Zipped
If NOVA is only saving `.nox` files, note that a `.nox` file is actually a `.zip` file containing XML and SQLite databases. You cannot read a `.nox` file directly while it's being written. You must either use the default `Database` folder where NOVA stores temporary `.sqlite` files during the run, or use the "Export ASCII" method mentioned above.
