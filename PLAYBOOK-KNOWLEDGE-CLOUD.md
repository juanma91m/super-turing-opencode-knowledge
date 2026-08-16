# Playbook: Engram Cloud local-first

## Boundary

- Cada PC usa su propio `~/.engram/engram.db` como source of truth local.
- Engram Cloud replica por proyecto; no está en el request path del MCP.
- Servidor y cliente se conectan por HTTP(S), aunque estén en la misma PC.
- Postgres es estado del servidor. Nunca montar `~/.engram` en Docker.
- No usar NFS, Syncthing o Dropbox para compartir SQLite.
- Qdrant no forma parte de esta fase.

## Servidor

Ver [`server/README.md`](./server/README.md). El deployment usa un Compose con
`engram-cloud` y `postgres` separados, sin publicar Postgres. `.env` contiene
secretos y no se versiona.

## Configuración de cada cliente

```bash
cp knowledge/knowledge-sync.conf.example ~/.config/opencode/knowledge-sync.conf
chmod 600 ~/.config/opencode/knowledge-sync.conf
```

Configurar:

- URL accesible del servidor;
- token de sync, nunca el token admin;
- allowlist comma-separated de proyectos existentes;
- timeout.

El archivo se parsea como datos y no ejecuta shell. Los proyectos se ordenan y
deduplican antes de sincronizar. Deben existir en `engram projects list` o estar
explícitamente enrolados —esto permite el primer pull de un cliente vacío— y
coincidir con la allowlist del servidor.

## Bootstrap explícito por proyecto

Ejecutar proyecto por proyecto. Nunca usar `--all` ni scripts masivos:

```bash
export ENGRAM_CLOUD_SERVER=http://127.0.0.1:18080
export ENGRAM_CLOUD_TOKEN='<sync token>'

engram cloud status
engram cloud enroll super-turing-opencode-knowledge
engram cloud upgrade doctor --project super-turing-opencode-knowledge
engram cloud upgrade repair --project super-turing-opencode-knowledge --dry-run
```

Si el doctor reporta metadata legacy, revisar el payload y el backup local antes
de ejecutar cualquier `--apply`. El addon no automatiza reparaciones. Solo con
aprobación explícita:

```bash
engram cloud upgrade repair --project super-turing-opencode-knowledge --apply
engram cloud upgrade bootstrap --project super-turing-opencode-knowledge --resume
```

Después:

```bash
~/.config/opencode/scripts/knowledge-push
~/.config/opencode/scripts/knowledge-pull
~/.config/opencode/scripts/knowledge-sync-status
```

## Semántica de los wrappers

- `knowledge-push`: sube cambios locales proyecto por proyecto.
- `knowledge-pull`: importa cambios remotos proyecto por proyecto.
- `knowledge-sync`: para cada proyecto hace pull y luego push.
- Si el pull de un proyecto falla, no hace push de ese proyecto en ese ciclo,
  pero continúa con los demás.
- Un lock machine-local evita solapamiento manual/timer.
- Los fallos quedan en el estado local y retornan non-zero; no borran mutations
  ni alteran `last_acked_seq` directamente.
- `ENGRAM_CLOUD_AUTOSYNC` se fuerza a `0` para no competir con el timer.

Estado operativo:

```bash
~/.config/opencode/scripts/knowledge-sync-status
journalctl --user -u opencode-knowledge-sync.service
```

## Timer horario

Instalar unidades en cualquier momento, pero habilitar el timer solo después de
que todos los proyectos configurados estén enrolados, reparados cuando aplique y
tengan un sync manual exitoso.

```bash
~/.config/opencode/scripts/knowledge-sync-timer install
~/.config/opencode/scripts/knowledge-sync-timer enable
~/.config/opencode/scripts/knowledge-sync-timer status
```

Usa `OnCalendar=hourly`, `Persistent=true` y jitter de hasta cinco minutos. El
timer puede fallar mientras el servidor está apagado; el MCP y SQLite local
siguen funcionando y el próximo ciclo vuelve a intentar.

Para remover solo la automatización:

```bash
~/.config/opencode/scripts/knowledge-sync-timer uninstall
```

No elimina config, secretos, SQLite ni estado de diagnóstico.
