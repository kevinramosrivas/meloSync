from pathlib import Path
import sys
import uvicorn

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

is_frozen = getattr(sys, "frozen", False)

# Safe stdio redirection when running as a windowless process or when stdout/stderr are None
if sys.stdout is None or sys.stderr is None or is_frozen:
    log_dir = Path.home() / ".melosync"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "melosync_backend.log"
    try:
        log_file = open(log_path, "a", encoding="utf-8", buffering=1)
        if sys.stdout is None:
            sys.stdout = log_file
        if sys.stderr is None:
            sys.stderr = log_file
    except Exception:
        pass

if __name__ == "__main__":
    if is_frozen:
        from src.api.main import app
        uvicorn.run(
            app,
            host="127.0.0.1",
            port=8000,
            log_level="info",
        )
    else:
        uvicorn.run(
            "src.api.main:app",
            host="127.0.0.1",
            port=8000,
            reload=True,
            log_level="info",
        )
