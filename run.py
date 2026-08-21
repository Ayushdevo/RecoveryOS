import os
import sys
import subprocess
import time
import signal

# Color definitions for log tags
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def log(tag, message, color=Colors.OKBLUE):
    print(f"{color}{Colors.BOLD}[{tag}]{Colors.ENDC} {message}")

def run_servers():
    backend_proc = None
    frontend_proc = None
    
    try:
        # 1. Start Backend FastAPI
        log("Backend", "Starting FastAPI server on http://127.0.0.1:8000 ...", Colors.OKGREEN)
        
        # Use venv python executable
        python_exe = os.path.join(".venv", "Scripts", "python.exe")
        if not os.path.exists(python_exe):
            # Fallback to system python if venv isn't structured this way
            python_exe = "python"
            
        backend_proc = subprocess.Popen(
            [python_exe, "-m", "uvicorn", "apps.backend.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        # Give backend a moment to boot and seed database
        time.sleep(3.0)
        
        # 2. Start Frontend Vite
        log("Frontend", "Starting Vite React dev server ...", Colors.HEADER)
        
        # Determine npm command for Windows
        npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
        
        frontend_proc = subprocess.Popen(
            [npm_cmd, "run", "dev"],
            cwd=os.path.join("apps", "dashboard"),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        
        log("System", "Both servers are running. Press Ctrl+C to terminate.", Colors.OKBLUE)
        log("System", "Dashboard URL: http://localhost:5173", Colors.OKGREEN)
        log("System", "Backend API docs: http://127.0.0.1:8000/docs", Colors.OKGREEN)
        
        # Non-blocking log printer loop
        import threading
        
        def print_output(proc, tag, color):
            for line in iter(proc.stdout.readline, ''):
                if line:
                    print(f"{color}[{tag}]{Colors.ENDC} {line.strip()}")
            proc.stdout.close()
            
        t1 = threading.Thread(target=print_output, args=(backend_proc, "Backend", Colors.OKGREEN), daemon=True)
        t2 = threading.Thread(target=print_output, args=(frontend_proc, "Frontend", Colors.HEADER), daemon=True)
        t1.start()
        t2.start()
        
        # Keep main thread alive
        while True:
            # Check if either failed
            if backend_proc.poll() is not None:
                log("Backend", "Server process terminated unexpectedly.", Colors.FAIL)
                break
            if frontend_proc.poll() is not None:
                log("Frontend", "Server process terminated unexpectedly.", Colors.FAIL)
                break
            time.sleep(1.0)
            
    except KeyboardInterrupt:
        log("System", "Shutdown signal received (Ctrl+C). Terminating subprocesses...", Colors.WARNING)
    except Exception as e:
        log("System", f"Launcher error: {e}", Colors.FAIL)
    finally:
        # Graceful cleanup
        if backend_proc:
            log("Backend", "Killing FastAPI server subprocess...", Colors.WARNING)
            backend_proc.terminate()
            backend_proc.wait()
        if frontend_proc:
            log("Frontend", "Killing Vite server subprocess...", Colors.WARNING)
            frontend_proc.terminate()
            frontend_proc.wait()
            
        log("System", "RecoveryOS has shut down.", Colors.OKBLUE)

if __name__ == "__main__":
    # Enable colors in windows cmd/powershell
    if sys.platform == 'win32':
        os.system('color')
    run_servers()
