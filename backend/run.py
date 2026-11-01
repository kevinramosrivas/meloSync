from pathlib import Path
import os
import socket
import sys
import uvicorn

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

is_frozen = getattr(sys, "frozen", False)

# Safe stdio redirection when running as a windowless process, background daemon, or when stdout/stderr are None
if sys.stdout is None or sys.stderr is None or is_frozen or "--no-reload" in sys.argv:
    log_dir = Path.home() / ".melosync"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "melosync_backend.log"
    try:
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        sys.stdout = log_file
        sys.stderr = log_file
    except Exception:
        pass


def start_parent_watchdog(parent_pid: int | None = None):
    """Monitors the parent process. If parent exits for any reason (Ctrl+C, crash, close), terminate immediately."""
    if not parent_pid:
        parent_pid = os.getppid() if hasattr(os, "getppid") else None
    if not parent_pid or parent_pid <= 1:
        return

    import threading
    import time

    def _watchdog_loop():
        if sys.platform == "win32":
            import ctypes
            kernel32 = ctypes.windll.kernel32
            SYNCHRONIZE = 0x00100000
            handle = kernel32.OpenProcess(SYNCHRONIZE, False, int(parent_pid))
            if not handle:
                os._exit(0)
            try:
                WAIT_TIMEOUT = 258
                while True:
                    time.sleep(0.5)
                    res = kernel32.WaitForSingleObject(handle, 0)
                    if res != WAIT_TIMEOUT:
                        os._exit(0)
            finally:
                kernel32.CloseHandle(handle)
        else:
            while True:
                time.sleep(0.5)
                try:
                    os.kill(parent_pid, 0)
                except OSError:
                    os._exit(0)

    t = threading.Thread(target=_watchdog_loop, daemon=True, name="ParentWatchdog")
    t.start()


def resolve_available_port(preferred_port: int, host: str = "127.0.0.1") -> int:
    """Return preferred_port if free to bind; otherwise request an OS ephemeral port."""
    if preferred_port > 0:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind((host, preferred_port))
                return preferred_port
            except OSError:
                pass

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


if __name__ == "__main__":
    import argparse
    import atexit
    import json
    import time

    parser = argparse.ArgumentParser(description="meloSync Backend Server")
    parser.add_argument("--port", type=int, default=8000, help="Preferred port to listen on")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host to listen on")
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="Disable auto-reload (used when spawned as a managed background child process)",
    )
    parser.add_argument(
        "--parent-pid",
        type=int,
        default=None,
        help="Parent process PID to monitor for automatic termination",
    )
    args, _ = parser.parse_known_args()

    # Iniciar watchdog de proceso padre para autoterminar en cuanto el cliente desktop se cierre
    start_parent_watchdog(args.parent_pid)

    target_host = args.host
    target_port = resolve_available_port(args.port, target_host)

    discovery_payload = {
        "port": target_port,
        "pid": os.getpid(),
        "timestamp": time.time(),
    }

    # 1. Write discovery file in ~/.melosync/active_port.json for Tauri & external tools
    discovery_file = Path.home() / ".melosync" / "active_port.json"
    try:
        discovery_file.parent.mkdir(parents=True, exist_ok=True)
        with open(discovery_file, "w", encoding="utf-8") as f:
            json.dump(discovery_payload, f)
    except Exception:
        pass

    # 2. In development mode, also write frontend/public/active_port.json for browser discovery
    public_discovery_file = None
    if not is_frozen:
        try:
            public_dir = backend_dir.parent / "frontend" / "public"
            if public_dir.exists():
                public_discovery_file = public_dir / "active_port.json"
                with open(public_discovery_file, "w", encoding="utf-8") as f:
                    json.dump(discovery_payload, f)
        except Exception:
            pass

    def cleanup_discovery():
        try:
            if discovery_file.exists():
                discovery_file.unlink()
            if public_discovery_file and public_discovery_file.exists():
                public_discovery_file.unlink()
        except Exception:
            pass

    atexit.register(cleanup_discovery)

    if is_frozen or args.no_reload:
        from src.api.main import app

        uvicorn.run(
            app,
            host=target_host,
            port=target_port,
            log_level="info",
        )
    else:
        uvicorn.run(
            "src.api.main:app",
            host=target_host,
            port=target_port,
            reload=True,
            log_level="info",
        )
