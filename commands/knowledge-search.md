---
description: Consulta el knowledge layer global por similitud semántica usando el wrapper aprobado.
agent: planner
subtask: false
---
Consultá el knowledge layer global de OpenCode.

Objetivo:
- ejecutar `bash ~/.config/opencode/scripts/knowledge_search.sh --query "$ARGUMENTS"`,
- usar el output como evidencia recuperada,
- resumir hallazgos útiles y distinguirlos de dudas o ruido.

Reglas:
- no escribir en Qdrant desde este comando,
- si el componente Qdrant del knowledge layer no está instalado o listo, explicitarlo y sugerir `bash ~/.config/opencode/scripts/install-knowledge-qdrant.sh`,
- no tratar un hit como fuente de verdad única; combinarlo con memoria curada y contexto actual,
- si el usuario necesita filtros más finos, explicitar qué args adicionales admite el wrapper.

Formato esperado:
- `## Hallazgos`
- `## Qué parece más relevante`
- `## Riesgos o límites`
- `## Siguientes pasos`
