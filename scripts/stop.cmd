@echo off
setlocal
cd /d "%~dp0\.."

echo ===========================================
echo   Deteniendo Project Zomboid (Docker)
echo ===========================================
echo.

docker compose down
if errorlevel 1 (
    echo [ERROR] Fallo al detener. Revisa los mensajes arriba.
    pause
    exit /b 1
)

echo.
echo Servidor detenido. Tus saves y configs se conservan.
pause
