import subprocess
import sys
import os
import time

def run_test():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    mock_script = os.path.join(base_dir, "mock_db.py")
    main_script = os.path.join(base_dir, "main.py")

    print("Starting mock database simulator in background...")
    mock_proc = subprocess.Popen([sys.executable, mock_script])

    # Give mock DB half a second to initialize the DB file
    time.sleep(0.5)

    print("Launching Nova Logger Application in Test Mode...")
    try:
        env = os.environ.copy()
        env["NOVA_TEST_MODE"] = "1"
        subprocess.run([sys.executable, main_script], env=env)
    finally:
        print("\nStopping background mock database process...")
        mock_proc.terminate()
        mock_proc.wait()
        print("Test session ended.")

if __name__ == "__main__":
    run_test()
