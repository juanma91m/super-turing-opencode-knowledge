# Playbook: Knowledge Layer (Engram + Qdrant)

Guía operativa para usar la capa `super-turing-opencode-knowledge` como addon separado de OpenCode.

## Componentes

- overview y gobernanza: este playbook
- componente Engram: `PLAYBOOK-KNOWLEDGE-ENGRAM.md`
- componente Qdrant: `PLAYBOOK-KNOWLEDGE-QDRANT.md`

## 1. Qué resuelve esta capa

- separar memoria curada de retrieval semántico,
- dejar un contrato claro entre **Engram** y **Qdrant**,
- permitir escritura gobernada y lectura más amplia sin abrir acceso bruto a un vector store.

## 2. Contrato base

### Engram

Usar para:

- decisiones,
- restricciones,
- preferencias,
- learnings durables,
- resúmenes de tickets o sesiones.

### Qdrant

Usar para:

- corpus grande,
- documentación reusable,
- material regenerable,
- retrieval semántico por similitud.

Regla rápida:

- si querés **recordar algo importante** entre sesiones, probablemente es Engram,
- si querés **buscar después entre mucho material**, probablemente es Qdrant.

## 3. Gobernanza de acceso

### Escritura

- no se escribe directo a Qdrant,
- la escritura pasa por `knowledge-curator` o por comandos/scripts explícitos aprobados,
- los wrappers determinísticos vigentes son:
  - `bash ~/.config/opencode/scripts/knowledge_store.sh ...`

### Lectura

- la lectura puede ser más amplia,
- los wrappers read-only vigentes son:
  - `bash ~/.config/opencode/scripts/knowledge_search.sh ...`
  - `bash ~/.config/opencode/scripts/knowledge_status.sh ...`

## 4. Runtime actual

- **Engram**:
  - binario local `~/.opencode/bin/engram`
  - DB local `~/.engram/engram.db`
  - source checkout gestionado `~/.local/src/engram-opencode-stack`
- **Qdrant**:
  - sin daemon,
  - Qdrant local file-based vía `QDRANT_LOCAL_PATH`,
  - estado machine-local por defecto en `~/.local/share/super-turing-opencode-knowledge/`.

## 5. Layout machine-local esperado

- `~/.local/share/super-turing-opencode-knowledge/.venv`
- `~/.local/share/super-turing-opencode-knowledge/qdrant`
- `~/.local/share/super-turing-opencode-knowledge/locks`

Instalación inicial por componente:

```bash
bash ~/.config/opencode/scripts/install-knowledge-engram.sh
bash ~/.config/opencode/scripts/install-knowledge-qdrant.sh
```

Wrapper de conveniencia:

```bash
bash ~/.config/opencode/scripts/install-knowledge.sh --all
```

## 6. Scopes y colecciones

### Global

Primer scope recomendado:

- colección: `global-opencode-knowledge`
- uso: docs, playbooks, referencias y material reusable del stack global.

### Proyectos

Cada overlay/proyecto debería especializar después:

- colección,
- metadata,
- corpus,
- comandos de ingesta,
- criterios de lectura.

No mezclar material global y de proyecto en la misma colección si el filtro/metadata todavía no está bien definido.

## 7. Metadata mínima recomendada

- `scope`
- `project`
- `source_type`
- `source_id`
- `title`
- `tags`
- `ingested_at`
- `ingested_by`
- `source_path` (si aplica)
- `chunk_index`
- `chunk_count`

## 8. Qué NO guardar

- `.env*`
- credenciales o secretos
- dumps sensibles
- contenido `<private>...</private>`
- memoria chica/durable que corresponde a Engram
- corpus sucio sin metadata mínima

## 9. Flujo recomendado v1

1. decidir si el material va a Engram o Qdrant,
2. si va a Qdrant y es global, usar `/knowledge-store-global <path>` o el wrapper correspondiente,
3. para resembrar el corpus global curado del stack, usar `/knowledge-index-global`,
4. validar con `/knowledge-status` y `/knowledge-search <query>`,
5. cuando un proyecto necesite retrieval propio, agregar solo el delta en su overlay local.

## 10. Boundary actual

Este repo ya es el source-of-truth del runtime y los assets operativos del knowledge layer.

Por ahora, la capa de compatibilidad cognitiva sigue parcialmente en `super-turing-opencode`:

- política genérica de memoria,
- hints de memoria,
- wiring MCP de Engram en el installer base.

Ese desacople queda para una fase posterior.
