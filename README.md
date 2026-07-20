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

### Desplegar en un VPS / servidor dedicado

Si despliegas este proyecto en un VPS (DigitalOcean, Hetzner, AWS, OVH, etc.), los cambios principales son:

1. **IPs en `.env`**:
   - `LOCAL_IP=` (vacio): en un VPS no hay "LAN" relevante para conectar; todo va por Internet.
   - `PUBLIC_IP=<IP del VPS>` o vacio: pon la IP que te dio el proveedor (ej: `203.0.113.45`), o dejala vacia para auto-deteccion via `api.ipify.org`.

2. **Firewall del VPS (iptables / ufw)**: en Linux no sirve la regla de Windows. Equivalente:
   ```bash
   # ufw (Ubuntu/Debian)
   sudo ufw allow 16261/udp
   sudo ufw allow 16262/udp
   sudo ufw allow 8766/udp
   sudo ufw allow 8767/udp
   # o con iptables
   sudo iptables -A INPUT -p udp --dport 16261 -j ACCEPT
   sudo iptables -A INPUT -p udp --dport 16262 -j ACCEPT
   sudo iptables -A INPUT -p udp --dport 8766 -j ACCEPT
   sudo iptables -A INPUT -p udp --dport 8767 -j ACCEPT
   ```
   La mayoria de proveedores de VPS tienen un firewall externo (security group) ademas del interno; abrilos en los dos sitios.

3. **Panel web**: por defecto escucha en `127.0.0.1:8080`. Para acceder desde fuera, configura un reverse proxy (nginx/caddy) con HTTPS, o cambia el `ports` del servicio `panel` en `docker-compose.yml` a `"8080:8080/tcp"` (sin `127.0.0.1:`). Mas info: [seccion del README o manual de cada proveedor].

4. **Persistencia**: los saves viven en `./pzdata/`. Haz backup regular de esa carpeta.

### Conectarse al servidor

1. Abrir Project Zomboid en Steam.
2. **Todos los jugadores** deben estar en la misma build exacta de la rama **unstable**. Si alguien esta en Build 41 estable, no podra conectar.
3. Menu principal > **Join** (Unirse) > Pestana **IP Direct**.
4. Escribir `IP:16261` (ej: `192.168.1.50:16261` o `83.45.123.78:16261`).
5. Si pusiste `SERVER_PASSWORD` en `.env`, te la pedira al entrar.

### Requisito de firewall (obligatorio para LAN e Internet)

`localhost` (127.0.0.1) funciona porque Windows no aplica firewall al loopback. Para conexiones desde la IP LAN o desde Internet, hace falta abrir los puertos UDP en Windows Defender Firewall. **Solo hay que hacerlo una vez por maquina**.

Abrir **PowerShell como Administrador** y ejecutar:

```powershell
New-NetFirewallRule `
  -DisplayName "PZ Server (Docker)" `
  -Direction Inbound `
  -Protocol UDP `
  -LocalPort 16261,16262,8766,8767 `
  -Action Allow `
  -Profile Any `
  -Enabled True
```

Verificar que esta activa:
```powershell
Get-NetFirewallRule -DisplayName "PZ Server (Docker)"
```
Debe mostrar `True` en `Enabled`.

Si tienes antivirus de terceros con firewall propio (Norton, Kaspersky, McAfee, Bitdefender, ESET, etc.), abre los mismos puertos en su panel tambien.

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
2. **Firewall de Windows**: comprueba que el firewall no este bloqueando UDP 16261. Ejecuta la regla del apartado ["Requisito de firewall"](#requisito-de-firewall-obligatorio-para-lan-e-internet) arriba.
3. **Pruebas locales**: conecta a `127.0.0.1:16261`. Si funciona local pero no desde la IP LAN, el problema es firewall (ver punto 2) o perfil de red Public.
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

> **Importante para Dokploy o VPS**: este repo ya usa **named volume `pzdata`** en vez de bind mounts `./pzdata`. Esto significa que `docker compose pull && up -d` en Dokploy **NO borra los saves**: el volumen Docker vive en `/var/lib/docker/volumes/` y Dokploy no lo toca. Si vienes del bind mount antiguo, sigue la guia de migracion abajo.

### Quiero dejar la imagen preparada para no perder tiempo

Tus saves y configs estan en `pzdata/`. Si reinstalas Docker Desktop o cambias de PC, basta con copiar `pzdata/` y `.env` (ambos ignorados por git).

### Migracion de bind mount a named volume (una sola vez)

Si antes guardabas saves en `./pzdata` (bind mount relativo) y los perdiste tras un redeploy, este fix es para ti. Tras aplicar el cambio del `docker-compose.yml`, todos los saves iran a un **named volume** que Dokploy no toca nunca.

```bash
# 1. Backup completo del bind mount actual (por si acaso)
cd /opt/dokploy/.../tu-app/
tar czf ~/pzdata_backup_$(date +%Y%m%d_%H%M%S).tar.gz pzdata/

# 2. Pull / Redeploy con el compose nuevo
git pull            # o desde Dokploy UI

# 3. Verificar que el named volume existe
docker volume ls | grep pzdata
# Esperado: serverproyectzomboid_pzdata (o <project>_pzdata)

# 4. Copiar los datos del bind mount viejo al named volume nuevo.
#    Ajusta <project>_pzdata segun el paso 3.
docker run --rm \
    -v $(pwd)/pzdata:/from:ro \
    -v serverproyectzomboid_pzdata:/to \
    alpine sh -c "cp -a /from/. /to/ && echo OK"

# 5. Verificar
docker run --rm -v serverproyectzomboid_pzdata:/data alpine ls /data/Saves/Multiplayer/servertest/

# 6. Reiniciar containers para que monten el volumen nuevo
docker compose restart
```

**Importante para Dokploy**: el named volume `pzdata` lo crea Docker automaticamente al hacer `docker compose up -d` despues de un primer deploy con el compose nuevo. Dokploy no recrea el volume en re-deploys posteriores — tus saves sobreviven.

### Backups automaticos del volumen

`scripts/backup-pzdata.sh` crea snapshots `.tar.gz` del volumen y los rota (>30 dias).

```bash
# Local: ejecutar a mano
scripts/backup-pzdata.sh /var/backups

# Cron en el VPS (diario a las 4am):
crontab -e
# Anade: 0 4 * * * /opt/dokploy/.../scripts/backup-pzdata.sh /var/backups/pzdata >> /var/log/pzbackup.log 2>&1
```

El script detecta automaticamente el nombre del volumen. Ver `scripts/backup-pzdata.sh` para instrucciones completas de restauracion.
