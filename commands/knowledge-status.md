---
description: Verifica el estado local del knowledge layer global por componente (Engram + Qdrant).
agent: agent-design
subtask: false
---
Auditá el estado del knowledge layer global.

Objetivo:
- ejecutar `bash ~/.config/opencode/scripts/knowledge_status.sh $ARGUMENTS`,
- verificar si Engram y/o Qdrant están instalados, usables y consistentes,
- resumir readiness, faltantes y colecciones detectadas.

Reglas:
- no escribir en Qdrant desde este comando,
- si falta el entorno de knowledge, sugerir instalación explícita en vez de simular éxito,
- separar `OK`, advertencias y pasos concretos.

Formato esperado:
- `## OK`
- `## Warnings`
- `## Errores`
- `## Siguientes pasos`
