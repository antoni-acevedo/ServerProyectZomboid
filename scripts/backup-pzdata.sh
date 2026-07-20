#!/bin/bash
# Backup del volumen `pzdata` del proyecto Project Zomboid server.
# USO:
#   ./scripts/backup-pzdata.sh                       # backup a /tmp/pzdata-backups
#   ./scripts/backup-pzdata.sh /var/backups          # backup a directorio custom
#
# Programar con cron:
#   0 4 * * * /opt/dokploy/.../scripts/backup-pzdata.sh /var/backups >> /var/log/pzbackup.log 2>&1
#
# Notas:
# - Funciona con named volumes (recomendado) y con bind mounts antiguos tambien.
# - El volumen se monta en solo lectura y se comprime con gzip en un container alpine.
# - Mantiene los ultimos 30 backups; los mas viejos se borran automaticamente.
# - Verificar que el nombre del volumen coincida. Si docker compose usa project prefix,
#   el nombre sera "<project>_pzdata" (ej: "serverproyectzomboid_pzdata").
#   El script detecta el nombre correcto automaticamente.

set -euo pipefail

BACKUP_DIR="${1:-/tmp/pzdata-backups}"
mkdir -p "$BACKUP_DIR"

# Detectar el nombre real del volumen. docker volume ls con formato.
VOLUME_NAME=$(docker volume ls --format '{{.Name}}' | grep -E '(^|_)pzdata$' | head -n1 || true)

if [ -z "$VOLUME_NAME" ]; then
    echo "[ERROR] No se ha encontrado un volumen llamado '*pzdata*'."
    echo "         Verifica con 'docker volume ls' y ajusta \$VOLUME_NAME en este script."
    exit 1
fi

TS=$(date +%Y%m%d_%H%M%S)
ARCHIVE_NAME="pzdata_${TS}.tar.gz"
ARCHIVE_PATH="${BACKUP_DIR}/${ARCHIVE_NAME}"

echo "[INFO] Backup del volumen: $VOLUME_NAME"
echo "[INFO] Destino:           $ARCHIVE_PATH"

# docker run --rm monta el volumen en read-only y crea el .tar.gz en /backup (que
# apunta al directorio destino del host).
docker run --rm \
    -v "${VOLUME_NAME}:/data:ro" \
    -v "${BACKUP_DIR}:/backup" \
    alpine \
    sh -c "tar czf /backup/${ARCHIVE_NAME} -C /data ."

echo "[OK] Backup creado: $ARCHIVE_PATH"
echo "[INFO] Tamano:"
du -sh "$ARCHIVE_PATH"

# Limpiar backups > 30 dias.
DELETED=$(find "$BACKUP_DIR" -name "pzdata_*.tar.gz" -mtime +30 -delete -print 2>/dev/null | wc -l || echo 0)
if [ "$DELETED" -gt 0 ] 2>/dev/null; then
    echo "[INFO] Backups antiguos (>30 dias) borrados: $DELETED"
fi

# Instrucciones de uso.
cat <<EOF

[INFO] Para restaurar este backup:
  1. Detener los containers:  docker compose stop
  2. Extraer el archivo:    tar xzf $ARCHIVE_PATH -C /tmp/pzdata_restore
  3. Copiar al volumen:     docker run --rm -v /tmp/pzdata_restore:/from -v ${VOLUME_NAME}:/to alpine sh -c "cp -a /from/. /to/"
  4. Reiniciar containers:  docker compose start

Alternativamente, backup sincronizado con Dokploy:
  - Dokploy no tiene "scheduled tasks" nativos en versiones recientes; usa cron del VPS.

EOF
