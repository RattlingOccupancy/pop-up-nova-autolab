import sqlite3
import time
import random
import os

DB_PATH = "temp_nova_data.sqlite"

def create_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE measurementpart (
            measurementpart_id INTEGER PRIMARY KEY,
            measurement_id INTEGER,
            cycle INTEGER,
            level INTEGER,
            tstep INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE point (
            point_id INTEGER PRIMARY KEY AUTOINCREMENT,
            measurementpart_id INTEGER,
            t REAL,
            y REAL
        )
    """)
    
    # Insert initial measurement part
    cursor.execute("""
        INSERT INTO measurementpart (measurementpart_id, measurement_id, cycle)
        VALUES (1, 1, 1)
    """)
    conn.commit()
    return conn

def simulate_nova():
    print(f"Starting simulated Nova data writer to {DB_PATH}")
    conn = create_db()
    cursor = conn.cursor()
    
    cycle_num = 1
    measurementpart_id = 1
    cycle_start = time.time()
    total_start = time.time()
    
    try:
        while True:
            now = time.time()
            total_time = now - total_start
            cycle_time = now - cycle_start
            
            # Simulate a cycle change every 60 seconds
            if cycle_time > 60:
                cycle_num += 1
                measurementpart_id += 1
                cycle_start = now
                cycle_time = 0
                # Insert new cycle into measurementpart
                cursor.execute("""
                    INSERT INTO measurementpart (measurementpart_id, measurement_id, cycle)
                    VALUES (?, 1, ?)
                """, (measurementpart_id, cycle_num))
                
            # Simulate current based on cycle and random noise
            base_current = 1e-6 * cycle_num 
            noise = random.uniform(-1e-8, 1e-8)
            current = base_current + noise
            
            # Insert data point
            cursor.execute("""
                INSERT INTO point (measurementpart_id, t, y)
                VALUES (?, ?, ?)
            """, (measurementpart_id, total_time, current))
            
            conn.commit()
            print(f"Wrote data: Cycle {cycle_num}, Time {total_time:.1f}s, Current {current:.2e}")
            
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping simulator.")
    finally:
        conn.close()

if __name__ == "__main__":
    simulate_nova()
