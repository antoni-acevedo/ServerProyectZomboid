@echo off
setlocal
cd /d "%~dp0\.."

echo ===========================================
echo   Reiniciando contenedor de Project Zomboid
echo ===========================================
echo.

docker compose restart zomboid
if errorlevel 1 (
    echo [ERROR] Fallo al reiniciar.
    pause
    exit /b 1
)

echo Servidor reiniciado.
pause
