# Instalación del addon knowledge

## Requisitos

- `opencode` ya instalado
- una instalación base funcional de OpenCode
- para Engram: `git`, `curl`, `tar` y Go o bootstrap automático de Go en Linux x86_64
- para Qdrant local: `python3` con soporte `venv`
- para backup/restore: `python3`, `tar` compatible vía stdlib y `flock` (normalmente provisto por `util-linux`)
- para Engram Cloud server: Docker Engine con Compose y `openssl`
- para sync horario en Linux: una sesión `systemd --user`

## Instalación recomendada

```bash
git clone https://github.com/juanma91m/super-turing-opencode-knowledge.git
cd super-turing-opencode-knowledge
bash scripts/install.sh --all
```

## Modos por componente

### Solo Engram

```bash
bash scripts/install.sh --engram-only
```

### Solo Qdrant

```bash
bash scripts/install.sh --qdrant-only
```

### Solo assets, sin bootstrap runtime

```bash
bash scripts/install.sh --assets-only
```

## Qué instala

- assets del knowledge layer en `~/.config/opencode/`
- overlays de autonomía para `agents/plan.md` y `agents/build.md`
- patch aditivo sobre `planner`, `master-dev` y `agent-design` si existen en la instalación destino
- skill backend-agnostic `memoria-durable-opencode`
- skill backend-specific `memoria-engram-opencode`
- plugin `plugins/engram-memory-hints.ts`
- merge del bloque MCP de Engram en `~/.config/opencode/opencode.json` cuando corresponde
- marker `~/.config/opencode/.opencode-knowledge-addon.json` con metadata de instalación y agentes augmentados
- `/memory-init` queda montado sobre `plan` para no depender de la existencia de `planner`
- si se pide runtime Engram:
  - `~/.opencode/bin/engram`
  - checkout gestionado de Engram para build/patch, reseteado al ref upstream fijado por el addon
- si se pide runtime Qdrant:
  - `~/.local/share/super-turing-opencode-knowledge/`
  - virtualenv local con `qdrant-client[fastembed]`

## Validación

```bash
bash scripts/status.sh
```

El status de Engram también informa el ref esperado/actual y si el patch
versionado está aplicado, para distinguir drift real del working tree sucio
esperado por el patch.

## Engram Cloud opcional

Después de instalar assets, copiar la plantilla machine-local:

```bash
cp ~/.config/opencode/knowledge/knowledge-sync.conf.example \
  ~/.config/opencode/knowledge-sync.conf
chmod 600 ~/.config/opencode/knowledge-sync.conf
```

Configurar URL, token y proyectos existentes. El deployment portable vive en
`server/`; el bootstrap y timer horario están en
[`PLAYBOOK-KNOWLEDGE-CLOUD.md`](./PLAYBOOK-KNOWLEDGE-CLOUD.md).

## Migración de estado a otra PC

En la PC origen:

```bash
bash ~/.config/opencode/scripts/knowledge_backup.sh \
  --output "$HOME/opencode-knowledge-backup.tar.gz"
```

En la PC destino:

1. instalar primero la misma versión del stack y de este addon,
2. copiar el archivo por un canal cifrado,
3. validar sin escribir,
4. cerrar OpenCode y todo proceso Engram,
5. restaurar con confirmación explícita.

```bash
bash ~/.config/opencode/scripts/knowledge_restore.sh \
  --archive "$HOME/opencode-knowledge-backup.tar.gz" \
  --verify-only

bash ~/.config/opencode/scripts/knowledge_restore.sh \
  --archive "$HOME/opencode-knowledge-backup.tar.gz" \
  --confirm-restore
```

Antes de reemplazar estado existente, restore deja un rollback bajo `~/.local/share/super-turing-opencode-knowledge/restore-backups/`. Las versiones de Engram, `qdrant-client` y la configuración de embeddings deben coincidir; cualquier excepción requiere un flag `--allow-*-mismatch` explícito.

## Interacción con el stack base

- `sync-opencode-stack.sh` normalmente no debería tocar `opencode.json`,
- `install-opencode-stack.sh` sí puede regenerarlo.

Si reinstalás `super-turing-opencode` después de tener este addon activo, conviene volver a correr:

```bash
bash scripts/install.sh --all
```

o al menos:

```bash
bash scripts/install.sh --engram-only
```

para reinyectar el MCP de Engram.

Y por componente:

```bash
bash ~/.config/opencode/scripts/knowledge_status_engram.sh
bash ~/.config/opencode/scripts/knowledge_status_qdrant.sh
```

## Desinstalación

```bash
bash scripts/uninstall.sh
```

Importante: por ahora la desinstalación remueve solo los assets instalados en `~/.config/opencode/`. El estado runtime/local de Engram y Qdrant queda intacto para evitar borrados destructivos por defecto.
