# Playbook: backup y restore del Knowledge Layer

## Objetivo

Migrar Engram y Qdrant local entre máquinas sin versionar bases, copiar locks efímeros ni compartir SQLite por red.

## Qué incluye el archivo

- `engram/engram.db`: snapshot SQLite consistente mediante la API de backup,
- `engram/engram-export.json`: export lógico para inspección o import manual,
- `qdrant/`: storage local, excluyendo `.lock`,
- `manifest.json`: versión del addon, runtime Engram, `qdrant-client`, embedding backend/model, tamaños y SHA-256.

No incluye binarios, virtualenvs, `knowledge_env.local.sh`, tokens ni otras credenciales.

Requiere `python3` y `flock`; restore usa `pgrep` cuando está disponible para rechazar procesos Engram activos.

## Crear backup

```bash
bash ~/.config/opencode/scripts/knowledge_backup.sh \
  --output "$HOME/opencode-knowledge-backup.tar.gz"
```

También se puede limitar el alcance:

```bash
bash ~/.config/opencode/scripts/knowledge_backup.sh --components engram
bash ~/.config/opencode/scripts/knowledge_backup.sh --components qdrant
```

El backup de Engram puede ejecutarse con el MCP activo porque usa la API SQLite online. El backup de Qdrant toma el lock cooperativo usado por los wrappers; no deben ejecutarse accesos directos externos al storage durante la copia.

## Verificar en destino

Instalar primero la misma revisión del addon y sus runtimes. Luego:

```bash
bash ~/.config/opencode/scripts/knowledge_restore.sh \
  --archive "$HOME/opencode-knowledge-backup.tar.gz" \
  --verify-only
```

La verificación rechaza path traversal, links, archivos extra, checksums inválidos y una DB Engram que no pase `PRAGMA integrity_check`.

## Restaurar

Cerrar OpenCode y cualquier `engram mcp`, `engram serve` o `engram tui`. Desde otra terminal:

```bash
bash ~/.config/opencode/scripts/knowledge_restore.sh \
  --archive "$HOME/opencode-knowledge-backup.tar.gz" \
  --confirm-restore
```

Restore compara por defecto:

- versión exacta de Engram,
- versión exacta de `qdrant-client`,
- backend y nombre del modelo de embeddings.

Los flags `--allow-engram-version-mismatch`, `--allow-qdrant-version-mismatch` y `--allow-embedding-mismatch` existen solo como escape hatch explícito; no usarlos para saltar una incompatibilidad no investigada.

Si ya había estado en destino, se preserva bajo:

```text
~/.local/share/super-turing-opencode-knowledge/restore-backups/<timestamp>/
```

Después de restaurar:

```bash
bash ~/.config/opencode/scripts/knowledge_status.sh
~/.opencode/bin/engram stats
```

Reiniciar OpenCode para que todos los MCP usen el estado restaurado.

## Seguridad y transporte

El archivo no copia secrets, pero contiene memoria durable, documentos fragmentados, embeddings y payloads. Por eso:

- mantener permisos `0600`,
- cifrarlo con una herramienta aprobada antes de subirlo o transportarlo,
- no guardarlo en Git,
- conservar el SHA-256 emitido por el comando para detectar corrupción de transporte.

Los checksums internos validan integridad accidental, no autenticidad frente a un atacante que pueda reemplazar archivo y manifest.
