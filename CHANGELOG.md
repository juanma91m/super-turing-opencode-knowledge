# Changelog

## 0.4.1

- abre `engram doctor`, sus modos `--plan`/`--dry-run`, `cloud upgrade doctor` y `cloud upgrade repair --dry-run` sobre SQLite en `mode=ro`, sin migraciones, startup repair ni persistencia de estado de upgrade,
- reemplaza las lecturas diagnósticas de `sync_state` que creaban filas por una consulta sin side effects,
- hace que `sync_mutation_required_fields` reutilice el mismo evaluador determinístico que Cloud repair para evitar drift entre diagnóstico y reparación,
- mantiene bloqueantes los defectos de proyectos enrolled, pero degrada backlog legacy de proyectos unenrolled a warning report-only sin sugerir enrollment como limpieza,
- agrega salida `--json` para `cloud upgrade doctor` con secuencias y SHA-256 de payload, sin exponer payloads crudos,
- agrega regresiones repetibles que comparan todas las tablas antes/después de doctor y dry-run.

## 0.4.0

- corrige `conflicts scan --semantic` para que el dry-run no persista relaciones ni mutaciones de sync,
- agrega ayuda real para `engram conflicts scan --help`,
- hace idempotentes los summaries por sesión mediante `session/<session-id>/summary`,
- agrega un plugin thin que propaga el `sessionID` real de OpenCode al summary,
- evita exports auxiliares en plugins auto-descubiertos, que OpenCode intentaría invocar como plugin factories durante el arranque,
- permite que `mem_session_summary` registre un `sessionID` real recién inyectado cuando todavía no existe en SQLite, sin relajar el contrato estricto de `mem_save`,
- alinea la superficie MCP operativa con adjudicación, detección de proyecto, diagnóstico y review, retirando `mem_delete` del wiring por defecto.

## 0.3.1

- la instalación portable usa `local-only` por defecto y deja Engram Cloud como opt-in explícito,
- agrega `scripts/preflight.sh` para validar dependencias locales antes de que el orquestador modifique el target,
- evita que una instalación completa no interactiva falle después de instalar la base por falta de modo Cloud.

## 0.3.0

- agrega deployment reproducible Engram Cloud + PostgreSQL 16 sin compartir el SQLite cliente,
- agrega wrappers `knowledge-push`, `knowledge-pull`, `knowledge-sync` y status agregado por proyecto,
- agrega configuración machine-local, lock de concurrencia y timer `systemd --user` horario,
- documenta bootstrap conservador, operación offline y backup/restore separado de PostgreSQL.

## [Unreleased]

### Added

- backup/restore portable de Engram y Qdrant local con manifest versionado, checksums SHA-256, backup SQLite online, export lógico de Engram, rollback automático y validaciones de compatibilidad
- extracción inicial del knowledge layer desde `super-turing-opencode` a `super-turing-opencode-knowledge`
- assets runtime y operativos de Engram y Qdrant en un solo repo con componentes separados
- scripts `install.sh`, `status.sh` y `uninstall.sh` para instalar el addon sobre `~/.config/opencode`
- `plugins/engram-memory-hints.ts` y `memoria-engram-opencode` como piezas backend-specific del addon

### Changed

- `KNOWLEDGE-MANIFEST.json` sube a `0.2.0`
- Engram sube del snapshot upstream `64bf163` al ref `1dafc0f`; el patch `source_agent` fue regenerado contra la arquitectura actual y el status ahora valida ref y patch aplicados
- `KNOWLEDGE-MANIFEST.json` sube a `0.1.1`
- `knowledge-reader` deja de forzar `variant: xhigh` y tanto `knowledge-reader` como `knowledge-curator` recortan tools UI irrelevantes para bajar costo fijo y costo de subagentes read-only sin afectar su rol
- `knowledge-curator` deja de forzar `variant: xhigh` como recorte conservador en un agente gobernado por wrappers y políticas explícitas
- el marker `.opencode-knowledge-addon.json` ahora persiste `repoDir` y `autonomyScript` para permitir recomposición automática de agentes aditivos desde el stack base
