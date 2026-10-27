# Changelog

## Unreleased

- Punto 6, etapa A: las plantillas opcionales `plan/build` condicionan solo su referencia a `analisis-tecnico-evidencia`; no es paso rutinario ni modifica memoria, permisos, generadores o bloques de autonomía. Sin despliegue ni reemplazo de agentes instalados.

- Punto 5: recuperación proporcional, reader sólo si aporta y está permitido, guardado durable por hito y summary por continuidad nueva. Pedidos explícitos, restricciones críticas, cierres locales y autoridad read-only se preservan; sin cambios de filtros, handlers o anotaciones.
- Se alinean los textos MCP, descripciones de uso, skill durable y autonomía; se eliminan ejemplos/categorías repetidos en la tool y bootstrap fijo por buckets. Se agregan checks de contrato y composición sin corridas de modelos; no se afirma mejora conductual o de latencia.
- Los errores determinísticos y respuestas ambiguas de escritura se tratan sin reintentos ciegos ni bypass. El render existente actualiza los bloques desde bases limpias; no se reemplaza el generador ni se cambian permisos por arrastre.

- Punto 4: instrucciones MCP derivadas de las tools realmente registradas, sin publicidad de herramientas ausentes ni promesas de loader; políticas disponibles y protocolo de conflictos preservados, con limitación explícita si falta adjudicación.
- El fix compartido respeta filtros distintos de OpenCode y Claude, sin cambiar allowlists, schemas, anotaciones o handlers. Tests focalizados del patch y probes nativos de metadatos con builds/SQLite aislados; no activa el candidato automáticamente.
- Se declara whitespace específico solo para el artefacto unified-patch (sus marcadores de contexto preceden tabs/líneas vacías); el código expandido se valida con `git apply --whitespace=error-all` y `gofmt`, sin relajar las reglas de las fuentes normales.

- `planner-helpers/knowledge.json` declara solo búsqueda/status del corpus para el ejecutor de análisis; no admite store, rebuild, cambio de DB ni endpoints arbitrarios desde el planner.

- agrega metadata cargable a `knowledge-governance-opencode` sin modificar su contrato ni wrappers; el asset compartido se propaga a Claude por el symlink existente.

- actualiza los agentes globales del addon de `openai/gpt-5.6-sol` a `openai/gpt-6.1-sol`.

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

- `knowledge-reader` y `knowledge-curator` dejan de sugerir skills genéricas que repetían su workflow explícito; se preservan permisos, wrappers, ownership Engram/Qdrant y el uso puntual de `knowledge-governance-opencode` definido en el propio prompt del curador
- `KNOWLEDGE-MANIFEST.json` sube a `0.2.0`
- Engram sube del snapshot upstream `64bf163` al ref `1dafc0f`; el patch `source_agent` fue regenerado contra la arquitectura actual y el status ahora valida ref y patch aplicados
- `KNOWLEDGE-MANIFEST.json` sube a `0.1.1`
- `knowledge-reader` deja de forzar `variant: xhigh` y tanto `knowledge-reader` como `knowledge-curator` recortan tools UI irrelevantes para bajar costo fijo y costo de subagentes read-only sin afectar su rol
- `knowledge-curator` deja de forzar `variant: xhigh` como recorte conservador en un agente gobernado por wrappers y políticas explícitas
- el marker `.opencode-knowledge-addon.json` ahora persiste `repoDir` y `autonomyScript` para permitir recomposición automática de agentes aditivos desde el stack base
