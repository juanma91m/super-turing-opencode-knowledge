# Playbook: Knowledge Component — Qdrant

## Qué resuelve

- corpus recuperable por similitud semántica,
- documentación reusable,
- material grande, regenerable o chunkable,
- retrieval gobernado sin abrir escritura directa libre al vector store.

## Cuándo usar Qdrant

- cuando necesitás **buscar después** entre mucho material,
- cuando el contenido es más grande que lo que conviene guardar como memoria curada,
- cuando querés reindexar un corpus versionado o regenerable.

## Qué NO usar Qdrant para

- decisiones chicas y durables,
- preferencias del usuario,
- learnings curados de alta señal que corresponden a Engram,
- secretos, `.env*`, dumps sensibles o `<private>...</private>`.

## Runtime actual

- sin daemon,
- Qdrant local file-based vía `QDRANT_LOCAL_PATH`,
- estado local por defecto en `~/.local/share/super-turing-opencode-knowledge/`.

## Instalación

```bash
bash ~/.config/opencode/scripts/install-knowledge-qdrant.sh
```

Wrapper de conveniencia backward-compatible:

```bash
bash ~/.config/opencode/scripts/install-knowledge.sh
```

## Estado

```bash
bash ~/.config/opencode/scripts/knowledge_status_qdrant.sh
```

O status agregado:

```bash
bash ~/.config/opencode/scripts/knowledge_status.sh
```

## Wrappers aprobados

- lectura:
  - `bash ~/.config/opencode/scripts/knowledge_search.sh ...`
  - `bash ~/.config/opencode/scripts/knowledge_status.sh ...`
- escritura gobernada:
  - `bash ~/.config/opencode/scripts/knowledge_store.sh ...`
  - `bash ~/.config/opencode/scripts/knowledge_seed_global.sh ...`

## Contrato con el stack base

- `knowledge-governance-opencode` decide Engram vs Qdrant,
- `knowledge-curator` gobierna la escritura,
- el stack base consume retrieval vía wrappers aprobados, no por acceso directo a Qdrant.

## Boundary actual

Scripts `knowledge_*`, el manifest `knowledge/global_seed_paths.txt`, este playbook y el runtime local Qdrant viven ya en `super-turing-opencode-knowledge`.
