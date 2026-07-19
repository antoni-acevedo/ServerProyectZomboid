import os
import secrets
import socket
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
SERVER_INI_NAME = os.getenv("SERVER_INI_NAME", "servertest.ini")
SANDBOX_NAME = os.getenv("SANDBOX_NAME", "servertest_SandboxVars.lua")
SERVER_INI = DATA_DIR / "Server" / SERVER_INI_NAME
SANDBOX_LUA = DATA_DIR / "Server" / SANDBOX_NAME
ALLOWED_FILES = {SERVER_INI_NAME: SERVER_INI, SANDBOX_NAME: SANDBOX_LUA}

ZOMBOID_CONTAINER = os.getenv("ZOMBOID_CONTAINER_NAME", "pz-zomboid")
PANEL_USER = os.getenv("PANEL_USERNAME", "admin")
PANEL_PASS = os.getenv("PANEL_PASSWORD", "admin")

app = FastAPI(title="PZ Web Panel", docs_url=None, redoc_url=None)
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
security = HTTPBasic()


def check_credentials(credentials: HTTPBasicCredentials = Depends(security)):
    ok_user = secrets.compare_digest(credentials.username, PANEL_USER)
    ok_pass = secrets.compare_digest(credentials.password, PANEL_PASS)
    if not (ok_user and ok_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
            headers={"WWW-Authenticate": 'Basic realm="PZ Panel"'},
        )
    return credentials.username


def read_ini_values(path: Path) -> dict[str, str]:
    """Read a PZ server INI as a flat dict. Sections are ignored; comments preserved."""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or s.startswith(";") or s.startswith("["):
            continue
        if "=" in s:
            key, _, value = s.partition("=")
            result[key.strip()] = value.strip()
    return result


def update_ini(path: Path, updates: dict[str, str]) -> None:
    """Update key=value pairs in-place. Preserves comments, sections, and unknown keys."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(
            "\n".join(f"{k}={v}" for k, v in updates.items()) + "\n",
            encoding="utf-8",
        )
        return
    lines = path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    new_lines = []
    for line in lines:
        s = line.strip()
        if s and not s.startswith("#") and not s.startswith(";") and not s.startswith("[") and "=" in s:
            key = s.partition("=")[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        new_lines.append(line)
    for key, value in updates.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")
    path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def docker_exec(args: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            ["docker", *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except FileNotFoundError:
        return 127, "", "docker binary not found"


def get_status() -> dict:
    code, out, err = docker_exec(["inspect", "-f", "{{.State.Running}}|{{.State.StartedAt}}", ZOMBOID_CONTAINER])
    if code != 0:
        return {"running": False, "error": err.strip() or "container not found"}
    running, started = out.strip().split("|", 1)
    return {"running": running.lower() == "true", "started": started}


def get_logs(tail: int = 200) -> str:
    code, out, err = docker_exec(["logs", f"--tail={tail}", ZOMBOID_CONTAINER])
    if code != 0:
        return f"Error leyendo logs: {err}"
    return out


def get_local_ip() -> tuple[str, bool]:
    """Return (ip, from_override). Override comes from LOCAL_IP env var."""
    override = os.getenv("LOCAL_IP", "").strip()
    if override:
        return override, True
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip, False
    except Exception:
        return "", False


_public_ip_cache: dict = {"ip": "", "ts": 0.0}


def get_public_ip() -> tuple[str, str]:
    """Return (ip, status). status: 'override' | 'cached' | 'fresh' | 'unavailable'."""
    override = os.getenv("PUBLIC_IP", "").strip()
    if override:
        return override, "override"
    now = time.time()
    if _public_ip_cache["ip"] and now - _public_ip_cache["ts"] < 3600:
        return _public_ip_cache["ip"], "cached"
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "5", "https://api.ipify.org"],
            capture_output=True, text=True, timeout=10,
        )
        ip = r.stdout.strip()
        if ip and all(c.isdigit() or c == "." for c in ip) and ip.count(".") == 3:
            _public_ip_cache["ip"] = ip
            _public_ip_cache["ts"] = now
            return ip, "fresh"
    except Exception:
        pass
    return _public_ip_cache.get("ip", ""), "unavailable"


def restart_server() -> tuple[bool, str]:
    code, out, err = docker_exec(["restart", ZOMBOID_CONTAINER], timeout=120)
    if code != 0:
        return False, err.strip() or f"exit code {code}"
    return True, "Servidor reiniciado correctamente."


@app.get("/healthz", include_in_schema=False)
def healthz():
    return PlainTextResponse("ok")


@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: str = Depends(check_credentials)):
    status_info = get_status()
    logs_tail = get_logs(40)
    server_section = read_ini_values(SERVER_INI)
    sandbox_exists = SANDBOX_LUA.exists()
    lan_ip, lan_from_override = get_local_ip()
    public_ip, public_status = get_public_ip()
    server_port = server_section.get("DefaultPort", "16261")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "status": status_info,
            "logs": logs_tail,
            "server": server_section,
            "files": list(ALLOWED_FILES.keys()),
            "sandbox_name": SANDBOX_NAME,
            "ini_name": SERVER_INI_NAME,
            "sandbox_exists": sandbox_exists,
            "message": request.query_params.get("msg"),
            "lan_ip": lan_ip,
            "lan_from_override": lan_from_override,
            "public_ip": public_ip,
            "public_ip_available": bool(public_ip) and public_status != "unavailable",
            "public_ip_status": public_status,
            "server_port": server_port,
        },
    )


@app.post("/save")
def save(
    name: str = Form(...),
    description: str = Form(""),
    public: str = Form("false"),
    max_players: int = Form(8),
    password: str = Form(""),
    pvp: str = Form("false"),
    pause_empty: str = Form("false"),
    pause_day: str = Form("false"),
    user: str = Depends(check_credentials),
):
    def b(v: str) -> str:
        return "true" if str(v).lower() == "true" else "false"

    update_ini(SERVER_INI, {
        "PublicName": name,
        "PublicDescription": description,
        "Public": b(public),
        "MaxPlayers": str(max_players),
        "Password": password,
        "PVP": b(pvp),
        "PauseEmpty": b(pause_empty),
    })

    ok, msg = restart_server()
    qs = "msg=" + ("Servidor reiniciado tras guardar." if ok else f"Guardado, pero fallo reinicio: {msg}")
    return RedirectResponse(url=f"/?{qs}", status_code=303)


@app.get("/editor", response_class=HTMLResponse)
def editor(
    request: Request,
    file: str = "",
    user: str = Depends(check_credentials),
):
    default_file = SERVER_INI_NAME if file == "" else file
    if default_file not in ALLOWED_FILES:
        raise HTTPException(404, "Archivo no permitido")
    path = ALLOWED_FILES[default_file]
    content = path.read_text(encoding="utf-8") if path.exists() else (
        f"-- {SANDBOX_NAME} se generara automaticamente la primera vez que inicies\n"
        "el servidor. Mientras tanto, puedes copiar aqui el contenido que quieras usar.\n"
        if default_file == SANDBOX_NAME else ""
    )
    return templates.TemplateResponse(
        "editor.html",
        {
            "request": request,
            "user": user,
            "file": default_file,
            "files": list(ALLOWED_FILES.keys()),
            "sandbox_name": SANDBOX_NAME,
            "ini_name": SERVER_INI_NAME,
            "content": content,
        },
    )


@app.post("/editor")
def editor_save(
    file: str = Form(...),
    content: str = Form(...),
    user: str = Depends(check_credentials),
):
    if file not in ALLOWED_FILES:
        raise HTTPException(404, "Archivo no permitido")
    path = ALLOWED_FILES[file]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    ok, msg = restart_server()
    qs = "msg=" + (f"Archivo {file} guardado." if ok else f"Guardado, pero fallo reinicio: {msg}")
    return RedirectResponse(url=f"/editor?file={file}&{qs}", status_code=303)


@app.post("/api/restart")
def api_restart(user: str = Depends(check_credentials)):
    ok, msg = restart_server()
    return JSONResponse({"ok": ok, "message": msg})


@app.get("/api/status")
def api_status(user: str = Depends(check_credentials)):
    return JSONResponse(get_status())


@app.get("/api/logs")
def api_logs(tail: int = 100, user: str = Depends(check_credentials)):
    return PlainTextResponse(get_logs(tail))
