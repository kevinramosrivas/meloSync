"""Script to package meloSync backend into a standalone Tauri sidecar executable."""

from pathlib import Path
import shutil
import subprocess
import sys

def build_sidecar():
    backend_dir = Path(__file__).resolve().parent
    frontend_bin_dir = backend_dir.parent / "frontend" / "src-tauri" / "bin"
    frontend_bin_dir.mkdir(parents=True, exist_ok=True)

    target_triple = "x86_64-pc-windows-msvc"
    output_exe_name = f"melosync-backend-{target_triple}.exe"
    target_path = frontend_bin_dir / output_exe_name

    print(f"[*] Packaging meloSync Python backend with PyInstaller...")
    print(f"[*] Target destination: {target_path}")

    pyinstaller_args = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onefile",
        "--clean",
        "--name",
        f"melosync-backend-{target_triple}",
        "--add-data",
        "src;src",
        "--hidden-import",
        "uvicorn.logging",
        "--hidden-import",
        "uvicorn.loops",
        "--hidden-import",
        "uvicorn.loops.auto",
        "--hidden-import",
        "uvicorn.protocols",
        "--hidden-import",
        "uvicorn.protocols.http",
        "--hidden-import",
        "uvicorn.protocols.http.auto",
        "--hidden-import",
        "uvicorn.protocols.websockets",
        "--hidden-import",
        "uvicorn.protocols.websockets.auto",
        "--hidden-import",
        "uvicorn.lifespan",
        "--hidden-import",
        "uvicorn.lifespan.on",
        "--hidden-import",
        "yt_dlp",
        "--hidden-import",
        "mutagen",
        "--hidden-import",
        "sqlalchemy",
        "run.py",
    ]

    subprocess.run(pyinstaller_args, cwd=str(backend_dir), check=True)

    dist_exe = backend_dir / "dist" / output_exe_name
    if dist_exe.exists():
        shutil.copy2(dist_exe, target_path)
        print(f"[OK] Sidecar binary successfully compiled and copied to: {target_path}")
    else:
        print(f"[ERROR] Built executable not found at {dist_exe}")
        sys.exit(1)

if __name__ == "__main__":
    build_sidecar()
