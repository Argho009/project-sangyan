import subprocess
import sys
import os
import time

def main():
    print("=======================================")
    print(" [>] Starting SANGYAN System")
    print("=======================================")
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    frontend_dir = os.path.join(base_dir, "frontend")
    
    # 1. Start the FastAPI backend
    print("Starting Backend on http://localhost:8000 ...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
        cwd=base_dir
    )
    
    # Give the backend a couple of seconds to initialize
    time.sleep(2)
    
    # 2. Start the Frontend HTTP server
    print("Starting Frontend on http://localhost:3000 ...")
    frontend_process = subprocess.Popen(
        [sys.executable, "-m", "http.server", "3000"],
        cwd=frontend_dir
    )
    
    print("\n[OK] SANGYAN is up and running!")
    print("[->] Open your web browser and go to: http://localhost:3000")
    print("\nPress Ctrl+C in this terminal to stop both servers.")
    
    try:
        # Wait for both processes
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\n\n[X] Stopping SANGYAN servers...")
        backend_process.terminate()
        frontend_process.terminate()
        
        # Ensure they are fully closed
        backend_process.wait()
        frontend_process.wait()
        print("Servers stopped successfully. Goodbye!")

if __name__ == "__main__":
    main()
