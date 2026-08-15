# Changelog

## [Unreleased]

### Added

- extracción inicial del knowledge layer desde `super-turing-opencode` a `super-turing-opencode-knowledge`
- assets runtime y operativos de Engram y Qdrant en un solo repo con componentes separados
- scripts `install.sh`, `status.sh` y `uninstall.sh` para instalar el addon sobre `~/.config/opencode`
- `plugins/engram-memory-hints.ts` y `memoria-engram-opencode` como piezas backend-specific del addon

### Changed

- Engram sube del snapshot upstream `64bf163` al ref `1dafc0f`; el patch `source_agent` fue regenerado contra la arquitectura actual y el status ahora valida ref y patch aplicados
- `KNOWLEDGE-MANIFEST.json` sube a `0.1.1`
- `knowledge-reader` deja de forzar `variant: xhigh` y tanto `knowledge-reader` como `knowledge-curator` recortan tools UI irrelevantes para bajar costo fijo y costo de subagentes read-only sin afectar su rol
- `knowledge-curator` deja de forzar `variant: xhigh` como recorte conservador en un agente gobernado por wrappers y políticas explícitas
- el marker `.opencode-knowledge-addon.json` ahora persiste `repoDir` y `autonomyScript` para permitir recomposición automática de agentes aditivos desde el stack base
