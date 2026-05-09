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
- backend de embeddings configurable: `fastembed` local o `ollama`,
- estado local por defecto en `~/.local/share/super-turing-opencode-knowledge/`.

## Backend de embeddings

### Default genérico

- backend: `fastembed`
- modelo por defecto: `sentence-transformers/all-MiniLM-L6-v2`

### Override local con Ollama

Si querés que el knowledge layer use un modelo de embeddings servido por Ollama, creá un override machine-local en:

```bash
~/.config/opencode/scripts/knowledge_env.local.sh
```

Ejemplo:

```bash
export OPENCODE_KNOWLEDGE_EMBEDDING_BACKEND=ollama
export OPENCODE_KNOWLEDGE_EMBEDDING_MODEL=snowflake-arctic-embed2:latest
export OPENCODE_KNOWLEDGE_OLLAMA_BASE_URL=http://127.0.0.1:11434
```

Los wrappers `knowledge_store.sh`, `knowledge_search.sh` y `knowledge_status_qdrant.sh` van a heredar ese override automáticamente.

### Cambio de modelo = reindexado

Si cambiás de modelo/backend de embeddings, **no mezcles vectores viejos y nuevos en la misma colección**.

- si la colección existente fue indexada con otra dimensión o semántica, hay que recrearla,
- Qdrant en este layer se trata como corpus **regenerable**, no como storage durable inmutable,
- después de recrear la colección, reindexá con `knowledge_seed_global.sh` o el seed del proyecto.

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
