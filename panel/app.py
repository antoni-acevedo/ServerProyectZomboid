import json
import os
import secrets
import socket
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Request, Response, status, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, PlainTextResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates

from schema import SCHEMA

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


# Estado de operaciones de power en background para evitar clicks duplicados.
# Permite maximo 5 min por operacion (TTL) por si el thread se cuelga.
_power_lock = threading.Lock()
_active_op: dict = {"kind": None, "started_at": 0.0}
_ACTIVE_OP_TTL = 300


def _can_start_op(kind: str) -> tuple[bool, str]:
    """Reserva la operacion. Devuelve (True, "") si ok; (False, msg) si ya hay una activa."""
    now = time.time()
    with _power_lock:
        if _active_op["kind"] is not None:
            age = now - (_active_op["started_at"] or 0)
            if age > _ACTIVE_OP_TTL:
                # TTL expirado: liberar el lock (probablemente un thread se murio)
                _active_op["kind"] = None
                _active_op["started_at"] = 0.0
            else:
                return False, f"Ya hay una operacion en curso ({_active_op['kind']}, hace {int(age)}s). Espera a que termine."
        _active_op["kind"] = kind
        _active_op["started_at"] = now
    return True, ""


def _finish_op():
    with _power_lock:
        _active_op["kind"] = None
        _active_op["started_at"] = 0.0


def _run_in_background(kind: str, args: list[str], timeout: int):
    """Lanza un comando docker en un thread daemon y libera el lock al acabar."""
    def _do():
        try:
            docker_exec(args, timeout=timeout)
        finally:
            _finish_op()
    threading.Thread(target=_do, daemon=True).start()


# --- Auto-shutdown por inactividad ---

AUTO_SHUTDOWN_CONFIG_FILE = DATA_DIR / "auto_shutdown.json"

_default_auto_config = {
    "enabled": False,
    "threshold_min": 15,
    "check_interval_s": 120,
    "whitelist": [],
}

_auto_lock = threading.Lock()
_auto_state: dict = {
    "config": dict(_default_auto_config),
    "last_player_count": None,
    "last_check_at": None,
    "empty_since": None,
    "scheduled_shutdown_at": None,
    "paused_until": None,
    "last_error": None,
    "next_check_at": None,
    "last_trigger_reason": None,
}
_auto_stop_event = threading.Event()


def _load_auto_shutdown_config() -> dict:
    """Lee config del disco. Devuelve defaults si no existe o falla."""
    try:
        if AUTO_SHUTDOWN_CONFIG_FILE.exists():
            raw = json.loads(AUTO_SHUTDOWN_CONFIG_FILE.read_text(encoding="utf-8"))
            cfg = dict(_default_auto_config)
            cfg.update({k: raw[k] for k in _default_auto_config if k in raw})
            cfg["whitelist"] = list(raw.get("whitelist", []))
            cfg["threshold_min"] = max(1, min(720, int(cfg["threshold_min"])))
            cfg["check_interval_s"] = max(15, min(1800, int(cfg["check_interval_s"])))
            cfg["enabled"] = bool(cfg["enabled"])
            return cfg
    except Exception as e:
        with _auto_lock:
            _auto_state["last_error"] = f"Error leyendo config: {e}"
    return dict(_default_auto_config)


def _save_auto_shutdown_config(cfg: dict) -> None:
    AUTO_SHUTDOWN_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    AUTO_SHUTDOWN_CONFIG_FILE.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _count_players_from_logs() -> tuple[int, str | None]:
    """Cuenta jugadores activos en los logs del server (joined - left/timeout).
    Devuelve (count, error_msg). count=-1 si fallo."""
    code, out, err = docker_exec(["logs", "--tail", "400", ZOMBOID_CONTAINER], timeout=10)
    if code != 0:
        return -1, (err or "docker logs fallo").strip()[:200]
    if not out:
        return -1, "logs vacios"

    joined = 0
    left = 0
    for line in out.splitlines():
        low = line.lower()
        if not low.strip():
            continue
        # Patrones comunes en logs PZ (best-effort, los logs no son 100% deterministas).
        is_join = (
            "joined the game" in low
            or "joined server" in low
            or ("joined" in low and " server" in low and "join" not in low.replace("joined", "", 1))
        )
        is_leave = (
            "left the game" in low
            or "disconnected" in low
            or "lost connection" in low
            or "timed out" in low
            or "kicked" in low
            or "banned" in low
        )
        if is_join:
            joined += 1
        elif is_leave:
            left += 1
    return max(0, joined - left), None


def auto_shutdown_loop() -> None:
    """Background thread: vigila jugadores y dispara stop cuando procede."""
    while not _auto_stop_event.is_set():
        try:
            with _auto_lock:
                cfg = _auto_state["config"]

            if not cfg["enabled"]:
                wait = min(60, cfg["check_interval_s"])
                _auto_stop_event.wait(wait)
                continue

            now = datetime.now(timezone.utc)
            now_iso = now.isoformat()
            with _auto_lock:
                paused_until_raw = _auto_state.get("paused_until")
                paused_until = datetime.fromisoformat(paused_until_raw) if paused_until_raw else None
                if paused_until and now < paused_until:
                    _auto_state["next_check_at"] = (now + timedelta(seconds=cfg["check_interval_s"])).isoformat()
                    _auto_stop_event.wait(cfg["check_interval_s"])
                    continue
                if paused_until and now >= paused_until:
                    _auto_state["paused_until"] = None
                # Marcar proximo check
                _auto_state["next_check_at"] = (now + timedelta(seconds=cfg["check_interval_s"])).isoformat()

            status = get_status()
            if not status.get("running"):
                with _auto_lock:
                    _auto_state["last_player_count"] = 0
                    _auto_state["empty_since"] = None
                    _auto_state["scheduled_shutdown_at"] = None
                _auto_stop_event.wait(cfg["check_interval_s"])
                continue

            player_count, err = _count_players_from_logs()
            with _auto_lock:
                _auto_state["last_player_count"] = player_count
                _auto_state["last_check_at"] = now_iso
                _auto_state["last_error"] = err

                if err is not None or player_count < 0:
                    pass
                elif player_count > 0:
                    _auto_state["empty_since"] = None
                    _auto_state["scheduled_shutdown_at"] = None
                else:
                    empty_iso = _auto_state["empty_since"]
                    if empty_iso is None:
                        _auto_state["empty_since"] = now_iso
                        empty_dt = now
                    else:
                        empty_dt = datetime.fromisoformat(empty_iso)
                    empty_seconds = (now - empty_dt).total_seconds()
                    threshold_seconds = cfg["threshold_min"] * 60
                    if empty_seconds >= threshold_seconds:
                        _auto_state["scheduled_shutdown_at"] = now_iso
                        _auto_state["last_trigger_reason"] = (
                            f"sin jugadores {int(empty_seconds//60)} min (umbral {cfg['threshold_min']} min)"
                        )
                        _run_in_background(
                            "stop",
                            ["stop", "--time", "30", ZOMBOID_CONTAINER],
                            timeout=45,
                        )
                        _auto_state["empty_since"] = None

        except Exception as ex:
            with _auto_lock:
                _auto_state["last_error"] = str(ex)[:200]
        finally:
            with _auto_lock:
                wait = _auto_state["config"]["check_interval_s"]
            _auto_stop_event.wait(wait)


@app.on_event("startup")
def _startup_auto_shutdown() -> None:
    """Arranca el scheduler al boot del panel. Lee config del disco."""
    global _auto_state
    _auto_stop_event.clear()
    cfg = _load_auto_shutdown_config()
    with _auto_lock:
        _auto_state["config"] = cfg
        _auto_state["last_error"] = None
    t = threading.Thread(target=auto_shutdown_loop, daemon=True, name="auto-shutdown")
    t.start()


@app.get("/api/auto-shutdown")
def api_get_auto_shutdown(user: str = Depends(check_credentials)):
    def _iso(v):
        return v.isoformat() if isinstance(v, datetime) else v

    with _auto_lock:
        snapshot = {
            "config": dict(_auto_state["config"]),
            "state": {
                "last_player_count": _auto_state["last_player_count"],
                "last_check_at": _iso(_auto_state["last_check_at"]),
                "next_check_at": _iso(_auto_state["next_check_at"]),
                "empty_since": _iso(_auto_state["empty_since"]),
                "scheduled_shutdown_at": _iso(_auto_state["scheduled_shutdown_at"]),
                "paused_until": _iso(_auto_state["paused_until"]),
                "last_error": _auto_state["last_error"],
                "last_trigger_reason": _auto_state["last_trigger_reason"],
            },
        }
    return JSONResponse(snapshot)


@app.post("/api/auto-shutdown")
async def api_set_auto_shutdown(request: Request, user: str = Depends(check_credentials)):
    body = await request.json()
    whitelist_raw = body.get("whitelist") or ""
    whitelist = [n.strip() for n in str(whitelist_raw).replace("\n", ",").split(",") if n.strip()]
    cfg = {
        "enabled": bool(body.get("enabled", False)),
        "threshold_min": max(1, min(720, int(body.get("threshold_min", 15)))),
        "check_interval_s": max(15, min(1800, int(body.get("check_interval_s", 120)))),
        "whitelist": whitelist,
    }
    _save_auto_shutdown_config(cfg)
    with _auto_lock:
        _auto_state["config"] = cfg
        _auto_state["paused_until"] = None
    return JSONResponse({"ok": True, "config": cfg})


@app.post("/api/auto-shutdown/cancel")
def api_cancel_auto_shutdown(user: str = Depends(check_credentials)):
    with _auto_lock:
        _auto_state["empty_since"] = None
        _auto_state["scheduled_shutdown_at"] = None
        _auto_state["last_trigger_reason"] = None
    return JSONResponse({"ok": True, "message": "Contador reseteado."})


@app.post("/api/auto-shutdown/pause")
def api_pause_auto_shutdown(request: Request, user: str = Depends(check_credentials)):
    minutes = 60
    try:
        minutes = int(request.query_params.get("minutes", "60"))
    except (TypeError, ValueError):
        pass
    minutes = max(5, min(720, minutes))
    until = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    with _auto_lock:
        _auto_state["paused_until"] = until.isoformat()
    return JSONResponse({"ok": True, "paused_until": until.isoformat(), "minutes": minutes})


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
            "schema": SCHEMA,
            "schema_keys": list(SCHEMA.keys()),
            "active_tab": request.query_params.get("tab") or "identity",
        },
    )


@app.post("/save")
async def save(request: Request, response: Response, user: str = Depends(check_credentials)):
    """Save settings for one tab, restart the container, return JSON so the
    page overlay can follow the restart progress live.
    Accepts either AJAX (expects JSON) or regular form submit (redirects).
    """
    accept = request.headers.get("accept", "").lower()
    wants_json = (
        "application/json" in accept
        or "xmlhttprequest" == request.headers.get("x-requested-with", "").lower()
        or request.headers.get("sec-fetch-mode", "").lower() == "cors"
    )

    body = await request.form()
    category = body.get("_category", "")
    received_keys = list(body.keys())
    if category not in SCHEMA:
        if wants_json:
            return JSONResponse({"ok": False, "message": "Pestana invalida", "category": category, "received": received_keys}, status_code=400)
        return RedirectResponse(url="/?msg=Pestana+invalida", status_code=303)

    updates: dict[str, str] = {}
    valid_keys = {f["key"] for f in SCHEMA[category]["fields"]}
    for k, v in body.multi_items():
        if k in valid_keys:
            value = str(v)
            if value.lower() == "true":
                value = "true"
            elif value.lower() == "false":
                value = "false"
            updates[k] = value

    if updates:
        update_ini(SERVER_INI, updates)

    ok, msg = restart_server()
    payload = {
        "ok": ok,
        "message": msg,
        "category": category,
        "updated": len(updates),
        "valid_keys_count": len(valid_keys),
        "received_keys": received_keys,
    }

    if wants_json:
        return JSONResponse(payload)

    if ok:
        status = "Guardado y servidor reiniciado."
    else:
        status = f"Guardado, pero el reinicio fallo: {msg}"
    return RedirectResponse(url=f"/?tab={category}&msg={status.replace(' ', '+')}", status_code=303)


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
    """Lanza docker restart en background y responde al instante.
    Evita timeouts HTTP del navegador/proxy (Dokploy, Traefik, etc.).
    """
    ok, msg = _can_start_op("restart")
    if not ok:
        return JSONResponse({"ok": False, "message": msg, "action": "restart"}, status_code=409)
    _run_in_background("restart", ["restart", ZOMBOID_CONTAINER], timeout=120)
    return JSONResponse({"ok": True, "message": "Orden de reinicio enviada. El contenedor se esta deteniendo y arrancando de nuevo (~30-60s).", "action": "restart"})


@app.post("/api/start")
def api_start(user: str = Depends(check_credentials)):
    """Lanza docker start en background. Responde al instante."""
    status = get_status()
    if status.get("running"):
        return JSONResponse({"ok": True, "message": "El servidor ya estaba encendido.", "action": "start"})
    ok, msg = _can_start_op("start")
    if not ok:
        return JSONResponse({"ok": False, "message": msg, "action": "start"}, status_code=409)
    _run_in_background("start", ["start", ZOMBOID_CONTAINER], timeout=30)
    return JSONResponse({"ok": True, "message": "Orden de encendido enviada. El contenedor JVM esta arrancando (~30-60s).", "action": "start"})


@app.post("/api/stop")
def api_stop(user: str = Depends(check_credentials)):
    """Lanza docker stop en background. Responde al instante.
    Evita timeouts HTTP cuando el JVM tarda en apagarse."""
    status = get_status()
    if not status.get("running"):
        _finish_op()  # limpiar cualquier estado residual por si acaso
        return JSONResponse({"ok": True, "message": "El servidor ya estaba detenido.", "action": "stop"})
    ok, msg = _can_start_op("stop")
    if not ok:
        return JSONResponse({"ok": False, "message": msg, "action": "stop"}, status_code=409)
    # --time 30: SIGTERM al JVM, espera 30s, despues SIGKILL automatico.
    _run_in_background("stop", ["stop", "--time", "30", ZOMBOID_CONTAINER], timeout=45)
    return JSONResponse({"ok": True, "message": "Orden de apagado enviada. Esperando que la JVM termine (~30-60s).", "action": "stop"})


@app.get("/api/status")
def api_status(user: str = Depends(check_credentials)):
    return JSONResponse(get_status())


@app.get("/api/logs")
def api_logs(tail: int = 100, user: str = Depends(check_credentials)):
    return PlainTextResponse(get_logs(tail))
