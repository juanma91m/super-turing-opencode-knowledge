# Changelog

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
