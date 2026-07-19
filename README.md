# Server Project Zomboid (Build 42) con Docker + Panel Web

Servidor dedicado de Project Zomboid (rama **Build 42 inestable**) corriendo en Docker, sin mods, con un panel web en `http://localhost:8080` para modificar toda la configuración de forma facil.

## Contenido

- [Requisitos](#requisitos)
- [Instalacion paso a paso](#instalacion-paso-a-paso)
- [Como arrancar / parar / ver logs](#como-arrancar--parar--ver-logs)
- [Como conectar tus amigos](#como-conectar-tus-amigos)
- [Como modificar la configuracion](#como-modificar-la-configuracion)
- [Steam Guard (primer arranque)](#steam-guard-primer-arranque)
- [Abrir puertos para Internet (port forwarding)](#abrir-puertos-para-internet-port-forwarding)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Problemas frecuentes](#problemas-frecuentes)

## Requisitos

- **Windows 10/11** con **Docker Desktop** instalado y el backend WSL2 activado.
  - Descarga: <https://www.docker.com/products/docker-desktop/>
  - Despues de instalar, asegurate de que el icono de Docker Desktop aparece en la bandeja sin errores.
- **Cuenta de Steam** con Project Zomboid comprado.
- Si vas a jugar con amigos desde fuera de tu red, acceso al router para abrir puertos.

## Instalacion paso a paso

### 1. Clonar o copiar este proyecto

Situate en la carpeta del proyecto:

```
cd C:\Users\Antoni\Desktop\Trabajo\Personal\ServerProyectZomboid
```

### 2. Configurar tus credenciales de Steam

Edita el archivo `.env` y rellena al menos:

```
STEAM_USER=tu_usuario_steam
STEAM_PASSWORD=tu_password_steam
ADMIN_PASSWORD=una_password_fuerte_para_admin
PANEL_PASSWORD=una_password_fuerte_para_el_panel
```

Opcionalmente ajusta: `SERVER_NAME`, `SERVER_MAX_PLAYERS`, `PVP`, `SERVER_PASSWORD`, `SERVER_PUBLIC`, etc.

> El archivo `.env` NO debe subirse a ningun repositorio (ya esta en `.gitignore`). Usa `.env.example` como plantilla.

### 3. Arrancar el servidor

Doble clic a `scripts\start.cmd` (o desde una terminal):

```
scripts\start.cmd
```

La primera vez tarda unos minutos:

1. Descarga la imagen Docker de Project Zomboid (~1.2 GB).
2. SteamCMD descarga los archivos del servidor dedicado Build 42 (~500 MB).
3. Genera `config\servertest.ini` y `config\SandboxVars.lua`.

Puedes seguir el progreso en otra terminal:

```
scripts\logs.cmd
```

Veras lineas como:

```
[hostname] INFO: Loading...
[hostname] INFO: World 'Muldraugh, KY' created.
```

Cuando veas algo asi el servidor esta listo.

### 4. Activar Build 42 en tu cliente Steam

Si tu juego esta en Build 41 estable y quieres conectarte a un servidor Build 42, debes cambiar la rama en Steam:

1. Abre tu biblioteca de Steam.
2. Click derecho sobre **Project Zomboid** > **Propiedades**.
3. Pestana **Betas** > selecciona **unstable - Build 42 Unstable**.
4. Espera a que descargue la actualizacion.
5. Repite esto en los PC de cada amigo que se vaya a conectar.

> El servidor y TODOS los clientes deben estar en la misma rama exacta. Si alguien esta en Build 41 estable, no podra conectarse.

## Como arrancar / parar / ver logs

| Accion              | Comando (Windows)       |
| ------------------- | ----------------------- |
| Arrancar            | `scripts\start.cmd`     |
| Parar               | `scripts\stop.cmd`      |
| Ver logs en vivo    | `scripts\logs.cmd`      |
| Reiniciar servidor  | `scripts\restart.cmd`   |
| Reconstruir imagen  | `scripts\start.cmd` (reconstruye si cambi Dockerfile) |

## Como conectar tus amigos

### En LAN (misma red Wi-Fi)

Tus amigos pueden unirse con:

```
IP_LOCAL:16261
```

Tu IP local suele ser `192.168.x.x`. La puedes ver con `ipconfig` en Windows.

### Desde Internet

1. Averigua tu IP publica: <https://whatismyip.com>
2. En tu router, abre los puertos **16261/UDP** y **16262/UDP** hacia la IP local de tu PC.
3. Tus amigos se conectan a `TU_IP_PUBLICA:16261` con la `SERVER_PASSWORD` si la definiste.

> Si tu ISP usa CGNAT (comun en España con algunos operadores moviles), el port forwarding no funcionara. En ese caso necesitarias un VPS o un servicio tipo hamachi/zerotier para jugar como si estuvieran en LAN.

### Conectarse al servidor

1. Abrir Project Zomboid.
2. Menu principal > **Join** (Unirse).
3. Pestana **IP Direct**.
4. Escribir `IP:16261` (ej: `192.168.1.50:16261`).
5. Usuario y contraseña de la cuenta Steam del jugador.
6. Si pusiste `SERVER_PASSWORD`, te la pedira al entrar.

## Como modificar la configuracion

### Opcion A: Panel web (recomendado)

Abre en tu navegador:

```
http://localhost:8080
```

- Te pedira usuario y contraseña (los de `PANEL_USERNAME` / `PANEL_PASSWORD` del `.env`).
- Cambias lo que quieras (nombre, max jugadores, PVP, etc.).
- Boton **Guardar y reiniciar** -> escribe en `servertest.ini` y reinicia el contenedor por ti.
- Para ajustes avanzados, usa los enlaces **Editor avanzado** (abre `servertest.ini`) o **SandboxVars.lua** (edicion cruda, ideal para tunear zombies, loot, profesiones, etc.).

El navegador refresca los logs automaticamente cada 15 segundos. Tambien puedes pulsar el boton **Reiniciar servidor** de la cabecera.

### Opcion B: Editar archivos a mano

Los archivos vivemte en `config\`:

- `config\servertest.ini` - ajustes de servidor (puerto, max jugadores, password, mods vacio, etc.)
- `config\SandboxVars.lua` - ajustes del mundo (zombies, loot, tiempo desde infeccion, etc.)

Edita con Notepad o VSCode, guarda y luego:

```
scripts\restart.cmd
```

### Que pasa cuando reinicio el servidor

El contenedor se reinicia y los jugadores conectados reciben un aviso de desconexion breve. Tus saves (mundo, personajes, etc.) NO se borran - estan en `saves\` que esta montado como volumen persistente.

## Steam Guard (primer arranque)

Si tu cuenta de Steam tiene **Steam Guard** activado (recomendado), la primera vez que descargue el servidor SteamCMD puede pedirte un codigo. Pasos:

1. Arranca normalmente con `scripts\start.cmd`.
2. Abre los logs con `scripts\logs.cmd`. Si ves algo como `Steam Guard code required`, necesitas meterlo.
3. Con el servidor ya levantado, en otra terminal:

   ```
   docker exec -it pz-zomboid /home/pzserver/steamcmd/steamcmd.sh +login TU_USUARIO +quit
   ```

   Te pedira el codigo una vez. A partir de ahi la sesion queda cacheada y no volvera a pedirlo (salvo que des logout manual o cambies de PC).

Si Steam Guard falla varias veces tu cuenta puede bloquearse temporalmente. Espera unos 30 minutos y vuelve a intentarlo si pasa.

## Abrir puertos para Internet (port forwarding)

En tu router (interfaz suele estar en `192.168.1.1` o `192.168.0.1`):

1. Busca la seccion **Port Forwarding**, **NAT**, **Virtual Server** o similar.
2. Anade dos reglas:

   | Nombre       | Protocolo | Puerto externo | Puerto interno | IP destino          |
   | ------------ | --------- | -------------- | -------------- | ------------------- |
   | PZ Game      | UDP       | 16261          | 16261          | IP local de tu PC   |
   | PZ Game 2    | UDP       | 16262          | 16262          | IP local de tu PC   |

   La IP local de tu PC la puedes ver con `ipconfig` (busca **Direccion IPv4**).

3. Guarda. Desde fuera, conecta con tu IP publica + `:16261`.

> Si tu IP publica cambia dinamicamente (la mayoria de ISPs), tus amigos tendran que pedirte la nueva IP cada vez. Soluciones gratuitas: DuckDNS, No-IP.

## Estructura del proyecto

```
ServerProyectZomboid/
|-- docker-compose.yml        # Orquesta ambos contenedores
|-- .env                      # Tus credenciales y configuracion (NO subir)
|-- .env.example              # Plantilla sin secretos
|-- README.md                 # Este archivo
|-- config/                   # Configs del servidor (volumen)
|   |-- servertest.ini        # Generado al primer arranque
|   +-- SandboxVars.lua       # Generado al primer arranque
|-- saves/                    # Saves de partidas (volumen, persistente)
|-- panel/                    # Panel web (FastAPI)
|   |-- Dockerfile
|   |-- requirements.txt
|   |-- app.py
|   +-- templates/
|       |-- index.html
|       +-- editor.html
+-- scripts/                  # Accesos directos para Windows
    |-- start.cmd
    |-- stop.cmd
    |-- restart.cmd
    +-- logs.cmd
```

## Problemas frecuentes

### El servidor no arranca y `logs.cmd` muestra "Steam Guard required"

Mira la seccion [Steam Guard](#steam-guard-primer-arranque) de este README.

### El servidor arranca pero no aparece en la lista publica

- Comprueba que `SERVER_PUBLIC=true` en `.env`.
- Asegurate de que el puerto 16261/UDP esta abierto en tu router y firewall de Windows.
- Si tu ISP usa CGNAT, no aparecera en la lista publica. Usa conexion por IP.

### Mis amigos ven "version mismatch" o no pueden conectar

Todos (servidor y clientes) deben estar en la misma build exacta de la rama `unstable` en Steam. Si uno reinicio su juego y se bajo una actualizacion, los demas tienen que reiniciar tambien.

### El panel web me pide usuario y contrasena

Es la autenticacion HTTP Basic definida en `.env` con `PANEL_USERNAME` / `PANEL_PASSWORD`. Si quieres cambiarlas, edita `.env` y reinicia el panel:

```
docker compose up -d --build panel
```

### El contenedor se reinicia solo / entra en crash loop

Mira los logs (`scripts\logs.cmd`). Las causas mas tipicas:

- Credenciales de Steam invalidas.
- `SandboxVars.lua` o `servertest.ini` con sintaxis rota por una edicion manual con caracteres extranos.

### Quiero cambiar el puerto del juego

Por defecto es `16261/UDP` y `16262/UDP`. Para cambiarlos:

1. Edita `.env` y anade `SERVER_PORT=27015` y `SERVER_PORT2=27016`.
2. Edita `docker-compose.yml` para mapear esos puertos (`${SERVER_PORT:-27015}:16261/udp`).
3. `scripts\restart.cmd`.

### Quiero volver a Build 41 estable

Cambia en `docker-compose.yml`:

```
image: cm2network/projectzomboid:latest   # en lugar de :b42
```

Y en `.env`:

```
BRANCH=public
```

Luego `scripts\restart.cmd`. Tus saves se conservan.
