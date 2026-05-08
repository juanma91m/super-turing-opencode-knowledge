---
description: Indexa el corpus global curado del stack en el knowledge layer usando un manifest versionado.
agent: knowledge-curator
subtask: false
---
Indexá el corpus global curado del stack en el knowledge layer.

Objetivo:
- ejecutar `bash ~/.config/opencode/scripts/knowledge_seed_global.sh $ARGUMENTS`,
- poblar o refrescar la colección global curada de docs del stack,
- mantener un seed repetible y versionado dentro de `super-turing-opencode-knowledge`.

Reglas:
- no indexar secretos, `.env*`, dumps sensibles ni contenido `<private>...</private>`,
- si el manifest incluye paths faltantes, reportarlos como `skipped` y no inventar contenido,
- si detectás que algo del manifest ya no corresponde a retrieval, reportalo como observación y no expandas el corpus por tu cuenta,
- validar al final con `knowledge_status_qdrant.sh`, `knowledge_status.sh` o una búsqueda puntual.

Formato esperado:
- `## Corpus indexado`
- `## Paths omitidos o faltantes`
- `## Validación básica`
- `## Riesgos o próximos ajustes`
