# Server Project Zomboid (Build 42) con Docker + Panel Web

Servidor dedicado de **Project Zomboid Build 42** corriendo en Docker sobre Windows, sin mods, con un panel web en `http://localhost:8080` para editar la configuracion desde el navegador.

## TL;DR - Quick start

1. Instala **Docker Desktop** ([link](https://www.docker.com/products/docker-desktop/)). Asegurate de tener **virtualizacion activada en BIOS** (VT-x en Intel, SVM en AMD). Verificar con:
   ```
   Get-WmiObject -Class Win32_Processor | Select-Object VirtualizationFirmwareEnabled
   ```
   Debe devolver `True`.

2. Edita `.env` y rellena al menos las passwords (las credenciales de Steam **ya no son necesarias**):
   ```
   notepad .env
   ```
   Cambia `ADMIN_PASSWORD` y `PANEL_PASSWORD` por valores fuertes.

3. Arranca:
   ```
   scripts\start.cmd
   ```
   La primera vez descarga ~2.3 GB (imagen con el server B42 inestable ya preinstalado).

4. Abre el panel:
   ```
   http://localhost:8080
   ```
   Usuario `admin` y la `PANEL_PASSWORD` que pusiste. Veras la IP LAN, IP publica, estado del server, logs y el formulario para editar configuracion.

5. Para conectarte desde el juego cliente: en Steam, click derecho sobre Project Zomboid > Propiedades > Betas > selecciona **unstable - Build 42 Unstable**. Reinicia Steam si hace falta. Luego en el juego: **Join > IP Direct** > `127.0.0.1:16261` (o la IP LAN que veas en el panel).

---

## Contenido

- [Requisitos](#requisitos)
- [Como arrancar / parar / ver logs](#como-arrancar--parar--ver-logs)
- [Como conectar tus amigos](#como-conectar-tus-amigos)
- [Como modificar la configuracion](#como-modificar-la-configuracion)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Variables de .env](#variables-de-env)
- [Problemas frecuentes](#problemas-frecuentes)

## Requisitos

- **Windows 10/11** con **Docker Desktop** instalado y el backend WSL2 activado.
- **Virtualizacion activada en BIOS** (VT-x / SVM). Sin esto Docker Desktop no arranca.
- **Project Zomboid** comprado en Steam.
- Si tus amigos van a jugar desde fuera de tu red, acceso al router para abrir puertos.

## Como arrancar / parar / ver logs

| Accion | Comando |
|---|---|
| Arrancar (build + start) | `scripts\start.cmd` |
| Parar | `scripts\stop.cmd` |
| Reiniciar solo el server | `scripts\restart.cmd` |
| Ver logs en vivo (Ctrl+C para salir) | `scripts\logs.cmd` |

La primera vez tarda unos minutos (descarga la imagen ~2.3 GB). Las siguientes son instantaneas.

## Como conectar tus amigos

### En LAN (misma red Wi-Fi)

1. Averigua tu IP local de Windows (busca **Direccion IPv4**):
   ```
   ipconfig
   ```
   Suele ser `192.168.x.x`.

2. Ponla en `.env` para que el panel la muestre correctamente:
   ```
   LOCAL_IP=192.168.1.50
   ```
   (Si lo dejas vacio, el panel intenta auto-detectar pero en Docker Desktop suele dar la IP del contenedor, que no es util.)

3. Tus amigos abren Project Zomboid (en Steam, todos en **unstable**), Join > IP Direct > `192.168.1.50:16261`.

### Desde Internet

1. En el panel veras tu **IP publica** auto-detectada (ej: `83.45.123.78`). Si no aparece, comprueba que tienes salida a internet desde el panel o pon `PUBLIC_IP=` en `.env`.

2. Abre los puertos en tu router hacia la IP local de tu PC:
   - `16261/UDP` - puerto principal del juego
   - `16262/UDP` - puerto UDP secundario
   - `8766/UDP` - Steam networking
   - `8767/UDP` - Steam networking

   La IP local la obtienes con `ipconfig` en Windows.

3. Tus amigos se conectan a `TU_IP_PUBLICA:16261`.

> **CGNAT**: si tu ISP usa Carrier-Grade NAT (algunos operadores en Espana), la IP publica aparece en el panel pero **no funcionara** para conexiones entrantes. Soluciones: tunel con ZeroTier / Radmin VPN, o un VPS.

### Conectarse al servidor

1. Abrir Project Zomboid en Steam.
2. **Todos los jugadores** deben estar en la misma build exacta de la rama **unstable**. Si alguien esta en Build 41 estable, no podra conectar.
3. Menu principal > **Join** (Unirse) > Pestana **IP Direct**.
4. Escribir `IP:16261` (ej: `192.168.1.50:16261` o `83.45.123.78:16261`).
5. Si pusiste `SERVER_PASSWORD` en `.env`, te la pedira al entrar.

## Como modificar la configuracion

### Opcion A: Panel web (recomendado)

Abre `http://localhost:8080`. Veras:

- **Seccion "Informacion de conexion"**: IP LAN + IP publica con botones Copiar.
- **Estado del servidor**: verde "en linea" o rojo "detenido".
- **Boton "Reiniciar servidor"**: reinicia el contenedor PZ.
- **Formulario de configuracion**: nombre, max jugadores, descripcion, password, PVP, pausa.
- **Editor avanzado**: editor raw de `servertest.ini` y `servertest_SandboxVars.lua` con resaltado basico.
- **Logs**: ultimas lineas del log del servidor, refresco automatico cada 15 segundos.

Al pulsar "Guardar y reiniciar", el panel escribe los cambios en `pzdata\Server\servertest.ini` y reinicia el contenedor automaticamente.

### Opcion B: Editar archivos a mano

Los archivos vivemte en `pzdata\Server\`:

- `servertest.ini` - ajustes de servidor (puerto, max jugadores, password, mods vacio, etc.)
- `servertest_SandboxVars.lua` - ajustes del mundo (zombies, loot, profesiones, etc.)

Edita con Notepad o VSCode, guarda y luego:

```
scripts\restart.cmd
```

> **Cuidado**: el formato de `servertest.ini` es plano `clave=valor` (sin secciones como `[Server]`). Si introduces secciones, el panel dejara de leerlo correctamente. Puedes usar `#` o `;` para comentarios.

## Estructura del proyecto

```
ServerProyectZomboid/
|-- docker-compose.yml          # Orquesta ambos contenedores
|-- .env                        # Tus credenciales y configuracion (NO subir a git)
|-- .env.example                # Plantilla sin secretos
|-- .gitignore
|-- README.md                   # Este archivo
|-- pzdata/                     # Volumen persistente: server data + saves
|   |-- Server/
|   |   |-- servertest.ini          # Config principal (se autogenera)
|   |   `-- servertest_SandboxVars.lua
|   |-- Saves/Multiplayer/servertest/   # Saves de partidas
|   |-- Logs/                         # Logs rotativos
|   `-- backups/                      # Backups automaticos de PZ
|-- panel/                      # Panel web (FastAPI)
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- app.py
|   `-- templates/
|       |-- index.html
|       `-- editor.html
`-- scripts/                    # Accesos directos para Windows
    |-- start.cmd
    |-- stop.cmd
    |-- restart.cmd
    `-- logs.cmd
```

## Variables de .env

### Identidad del servidor
- `SERVER_NAME` - nombre interno (no se usa directamente).
- `SERVER_PUBLIC_NAME` - nombre que aparece en la lista publica de servidores.
- `SERVER_PUBLIC_DESCRIPTION` - descripcion que ven los jugadores.
- `SERVER_PUBLIC` - `true` para aparecer en lista publica de Steam; `false` para solo por IP directa.

### Puertos
- `SERVER_PORT` - puerto principal (default `16261` UDP).
- `SERVER_PORT2` - puerto UDP secundario (default `16262`).

### Reglas
- `SERVER_PASSWORD` - password para unirse (vacio = sin password).
- `SERVER_MEMORY` - RAM JVM (default `2048m`, sube a `4096m` si tienes muchos jugadores).
- `RCON_PASSWORD` - password para RCON (vacio = desactivado).

### Admin in-game
- `ADMIN_PASSWORD` - password del usuario `admin` dentro del juego. Requerida solo en el primer arranque; luego puedes borrarla para que no quede en logs.

### Panel web
- `PANEL_USERNAME` - usuario del panel (default `admin`).
- `PANEL_PASSWORD` - password del panel.

### IPs (opcional, mejoran la deteccion del panel)
- `LOCAL_IP` - tu IP de LAN. Si la dejas vacia, el panel intenta auto-detectar (en Docker Desktop suele dar la IP del contenedor, no util).
- `PUBLIC_IP` - tu IP publica. Si la dejas vacia, el panel la detecta via `api.ipify.org` y la cachea 1 hora. Sobreescribela si tienes DuckDNS o dominio dinamico.

## Problemas frecuentes

### Docker Desktop atascado en "iniciando infinitamente"

Causa habitual: **virtualizacion desactivada en BIOS**. Verificar:
```
Get-WmiObject -Class Win32_Processor | Select-Object VirtualizationFirmwareEnabled
```
Si devuelve `False`: reinicia PC, entra a BIOS (Supr / F2 / F10 segun fabricante), busca `Intel Virtualization Technology` o `AMD SVM`, activala, guarda.

Si devuelve `True` pero Docker sigue colgado:
1. Sal de Docker Desktop (icono en bandeja > Quit).
2. PowerShell como Administrador: `wsl --shutdown` y `wsl --update`.
3. Vuelve a abrir Docker Desktop.

### Panel dice "servidor detenido" pero el contenedor esta corriendo

Espera 30 segundos y recarga. El panel consulta a Docker y a veces hay un pequeno delay.

Tambien puedes pulsar el boton "Reiniciar servidor" en el panel.

### El juego cliente dice "The server failed to respond" o no encuentra el server

1. **Todos en la misma build**: Steam > Project Zomboid > Propiedades > Betas > **unstable - Build 42 Unstable**. Si alguno esta en `public` (B41 estable), no podra conectar.
2. **Firewall de Windows**: comprueba que el firewall no este bloqueando UDP 16261. Docker Desktop deberia crear reglas automaticas (`Docker Desktop Backend` con `UDP Any`). Si no estan, anade una regla manual:
   ```
   New-NetFirewallRule -DisplayName "PZ Server" -Direction Inbound -Protocol UDP -LocalPort 16261,16262,8766,8767 -Action Allow
   ```
3. **Pruebas locales**: conecta a `127.0.0.1:16261`. Si funciona local pero no desde la IP LAN, el problema es firewall o router.
4. **Pruebas remotas**: abre los puertos en tu router (seccion "Desde Internet" arriba). Si tienes CGNAT, no funcionara.

### El server arranca pero crashea al guardar el INI desde el panel

El parser del panel espera formato plano `clave=valor` sin secciones. Si abres `servertest.ini` y metes `[Server]\nclave=valor` a mano, el panel lo dejara de leer. Restaura desde la copia de seguridad:
```
copy pzdata\backups\startup\backup_1.zip pzdata\
```
(o el backup mas reciente que tengas) y reinicia el contenedor.

### El panel muestra una IP rara en LAN (172.18.x.x)

Es la IP interna del contenedor Docker, no tu IP real. Pon `LOCAL_IP=tu_ip_real` en `.env` y reinicia el panel:
```
docker compose restart panel
```
Tu IP real la ves con `ipconfig` en Windows (Direccion IPv4).

### Quiero volver a Build 41 estable

Edita `docker-compose.yml`:
```yaml
image: danixu86/project-zomboid-dedicated-server:latest-unstable
```
cambia a:
```yaml
image: danixu86/project-zomboid-dedicated-server:latest
```
Y `.env`:
```
# (comenta o elimina esta linea)
# BRANCH=unstable
```
Luego:
```
scripts\restart.cmd
```

### Quiero empezar una partida de cero (borrar saves)

```
scripts\stop.cmd
```
Borra el contenido de `pzdata\Saves\Multiplayer\servertest\` (NO la carpeta entera, solo lo de dentro). Luego:
```
scripts\start.cmd
```

### Cambiar dificultad del mundo (zombies, loot, profesiones)

Usa el editor del panel: **Editor SandboxVars.lua**. Edita `ZombiePopulationMultiplier`, `LootAbundance`, etc. y pulsa Guardar y reiniciar.

### Cambiar la RAM del servidor

Edita `.env`:
```
SERVER_MEMORY=4096m
```
Y reinicia:
```
docker compose restart zomboid
```

### Actualizar a una nueva build (ej: cuando salga 42.20.0)

```
scripts\stop.cmd
docker compose pull
scripts\start.cmd
```

**Aviso**: en Build 42 inestable, cada parche semanal puede requerir wipe (borrar saves) para evitar corrupcion. Haz backup de `pzdata\Saves\Multiplayer\servertest\` antes de actualizar.

### Quiero dejar la imagen preparada para no perder tiempo

Tus saves y configs estan en `pzdata/`. Si reinstalas Docker Desktop o cambias de PC, basta con copiar `pzdata/` y `.env` (ambos ignorados por git).
