@echo off
echo ========================================================
echo    meloSync - Entorno de Desarrollo con Hot-Reload
echo ========================================================
echo.
echo [1/2] Iniciando Backend FastAPI (http://127.0.0.1:8000)...
start /min "meloSync Backend" cmd /k "cd backend && python run.py"

echo [2/2] Iniciando Frontend Angular y Ventana Tauri (http://localhost:4200)...
cd frontend
npm run dev:desktop
