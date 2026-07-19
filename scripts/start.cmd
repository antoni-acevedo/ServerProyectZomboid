@echo off
setlocal
cd /d "%~dp0\.."

echo ===========================================
echo   Iniciando Project Zomboid (Docker)
echo ===========================================
echo.

docker --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker no esta instalado o no esta en el PATH.
    echo          Instala Docker Desktop desde https://www.docker.com/products/docker-desktop/
    pause
    exit /b 1
)

if not exist .env (
    echo [AVISO] No existe .env. Copiando .env.example...
    copy /Y .env.example .env >nul
    echo         Edita el archivo .env con tu usuario/password de Steam antes de continuar.
    pause
    exit /b 1
)

docker compose up -d --build
if errorlevel 1 (
    echo [ERROR] Fallo docker compose. Revisa los mensajes arriba.
    pause
    exit /b 1
)

echo.
echo ===========================================
echo   Servidor arrancando en segundo plano
echo ===========================================
echo   - Panel web: http://localhost:8080
echo   - Logs: scripts\logs.cmd
echo   - Puerto juego: 16261/UDP (16262/UDP)
echo ===========================================
echo.
echo La primera vez tarda unos minutos (descarga imagen y server).
echo Puedes ver el progreso con scripts\logs.cmd
pause
