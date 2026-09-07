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

## Superficie MCP y sesiones

- el addon expone las tools core de memoria más `mem_judge`,
  `mem_current_project`, `mem_doctor` y `mem_review`,
- `mem_delete` queda fuera de la superficie operativa por defecto,
- el plugin `engram-session-context.ts` inyecta el `sessionID` real de OpenCode
  solo en `engram_mem_session_summary` y preserva cualquier ID explícito,
- si ese ID todavía no existe en SQLite, `mem_session_summary` resuelve el
  proyecto con las reglas normales y crea la sesión antes de guardar; esta
  excepción no relaja el rechazo de sesiones desconocidas en `mem_save`,
- cada summary con un ID canónico usa
  `topic_key=session/<session-id>/summary`: repetir una sesión actualiza la misma
  observación y otra sesión crea una distinta; IDs explícitos no canónicos usan
  un segmento hash estable para no colisionar al normalizar o truncar.

OpenCode trata **cada export** de un archivo auto-descubierto bajo `plugins/*.ts`
como una plugin factory. Esos módulos deben exportar únicamente factories que
devuelvan un objeto de hooks; helpers internos no deben llevar `export`.

`engram conflicts scan --semantic` puede ejecutar llamadas al runner también en
dry-run, pero sin `--apply` no persiste relaciones ni mutaciones de sync. Usar
`engram conflicts scan --help` para revisar flags y presupuesto antes de correrlo.

## Réplica Cloud opcional

Cada PC conserva SQLite local y puede sincronizar una allowlist explícita de
proyectos contra Engram Cloud:

```bash
~/.config/opencode/scripts/knowledge-push
~/.config/opencode/scripts/knowledge-pull
~/.config/opencode/scripts/knowledge-sync
~/.config/opencode/scripts/knowledge-sync-status
```

El servidor, bootstrap seguro y timer horario están documentados en
[`PLAYBOOK-KNOWLEDGE-CLOUD.md`](./PLAYBOOK-KNOWLEDGE-CLOUD.md).

## Contrato con el stack base

- el stack base sigue decidiendo **cuándo** consultar memoria,
- `memoria-durable-opencode` sigue modelando la política cognitiva,
- este componente resuelve el backend/runtime de Engram y su MCP.

## Boundary actual

Todo lo que sea build, patch, binario, DB y status de Engram vive ya en `super-turing-opencode-knowledge`.
La política genérica de memoria y el wiring MCP de compatibilidad siguen temporalmente en el stack base y se desacoplan después.
