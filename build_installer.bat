@echo off
echo ========================================================
echo    meloSync - Pipeline de Compilacion para Produccion
echo ========================================================
echo.
echo [1/3] Compilando Backend Python a Binario Sidecar con PyInstaller...
cd backend
python build_sidecar.py
if %ERRORLEVEL% NEQ 0 (
    echo [!] Error al compilar el backend.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Compilando Frontend Angular y Empaquetando con Tauri...
cd ../frontend
npm run build
npx tauri build
if %ERRORLEVEL% NEQ 0 (
    echo [!] Error al compilar Tauri.
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo ========================================================
echo  [✓] Instalador generado exitosamente en:
echo      frontend\src-tauri\target\release\bundle\nsis\
echo ========================================================
pause
