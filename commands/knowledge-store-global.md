---
description: Cura e indexa material reusable del stack global en el knowledge layer usando el wrapper aprobado.
agent: knowledge-curator
subtask: false
---
Curá e indexá material reusable del stack global en el knowledge layer.

Objetivo:
- ejecutar `bash ~/.config/opencode/scripts/knowledge_store.sh store-path --scope global --project opencode-stack --collection global-opencode-knowledge --source-type stack-doc --path "$ARGUMENTS"`,
- decidir si el material realmente corresponde a Qdrant y no a Engram,
- dejar una validación básica posterior con `knowledge_search.sh`, `knowledge_status_qdrant.sh` o `knowledge_status.sh`.

Reglas:
- no indexar secretos, `.env*`, dumps sensibles ni contenido `<private>...</private>`,
- si el path no existe o el material no parece apto para retrieval, frená y explicalo,
- mantené el corpus global libre de detalle específico de un proyecto concreto,
- si el material es mejor candidato para memoria curada, decilo y no lo fuerces a Qdrant.

Formato esperado:
- `## Material evaluado`
- `## Decisión de curación`
- `## Escritura realizada`
- `## Validación básica`
- `## Riesgos o límites`
