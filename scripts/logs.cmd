@echo off
setlocal
cd /d "%~dp0\.."

echo ===========================================
echo   Logs de Project Zomboid (Ctrl+C para salir)
echo ===========================================
echo.

docker compose logs -f zomboid
