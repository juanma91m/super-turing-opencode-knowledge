# Playbook: Knowledge Component — Engram

## Qué resuelve

- memoria curada y durable entre sesiones,
- decisiones, restricciones, preferencias y learnings de alta señal,
- continuidad semántica chica, no corpus grande.

## Cuándo usar Engram

- cuando algo debe **recordarse** entre sesiones,
- cuando el valor está en el resumen curado y no en el texto completo,
- cuando necesitás `topic_key`, promoción, actualización o purga.

## Qué NO usar Engram para

- corpus grande regenerable,
- documentación extensa pensada para búsqueda semántica,
- chunks numerosos o material recuperable mejor apto para Qdrant.

## Runtime actual

- binario local: `~/.opencode/bin/engram`
- DB local: `~/.engram/engram.db`
- source checkout gestionado: `~/.local/src/engram-opencode-stack`

## Instalación / rebuild

```bash
bash ~/.config/opencode/scripts/install-knowledge-engram.sh
```

Alias legacy todavía soportado:

```bash
bash ~/.config/opencode/scripts/install-engram.sh
```

## Estado

```bash
bash ~/.config/opencode/scripts/knowledge_status_engram.sh
```

## Contrato con el stack base

- el stack base sigue decidiendo **cuándo** consultar memoria,
- `memoria-engram-opencode` sigue modelando la política cognitiva,
- este componente resuelve el backend/runtime de Engram y su MCP.

## Boundary actual

Todo lo que sea build, patch, binario, DB y status de Engram vive ya en `super-turing-opencode-knowledge`.
La política genérica de memoria y el wiring MCP de compatibilidad siguen temporalmente en el stack base y se desacoplan después.
