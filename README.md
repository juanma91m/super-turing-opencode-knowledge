# OpenCode Knowledge Add-on

Addon separado para el knowledge layer de OpenCode.

## Qué contiene

Este repo agrupa dos componentes relacionados pero separados:

- **Engram**: memoria curada, durable y de alta señal
- **Qdrant**: retrieval sobre corpus recuperable y regenerable

## Supuesto operativo actual

Este addon asume una instalación base de OpenCode ya funcional, típicamente con `super-turing-opencode` como capa principal en `~/.config/opencode/`.

## Qué mueve fuera del stack base

Este repo pasa a ser dueño de:

- installers runtime de Engram y Qdrant,
- status por componente,
- wrappers `knowledge_*`,
- comandos `/knowledge-*`,
- `plugins/engram-memory-hints.ts`,
- `knowledge-curator`,
- `knowledge-governance-opencode`,
- `memoria-engram-opencode` como skill backend-specific,
- wiring del MCP de Engram sobre `~/.config/opencode/opencode.json`,
- playbooks y manifest del knowledge layer,
- patch versionado de Engram.

## Qué NO mueve todavía

La capa de compatibilidad cognitiva sigue temporalmente en `super-turing-opencode`, por ejemplo:

- `memoria-durable-opencode`,
- y el wiring MCP de Engram en el installer base.

Eso se desacopla en una fase posterior.

## Instalación

Guía más detallada: [`INSTALLATION.md`](./INSTALLATION.md)

```bash
git clone https://github.com/juanma91m/super-turing-opencode-knowledge.git
cd super-turing-opencode-knowledge
bash scripts/install.sh --all
```

Modos útiles:

```bash
bash scripts/install.sh --engram-only
bash scripts/install.sh --qdrant-only
bash scripts/install.sh --all
bash scripts/install.sh --assets-only
```

## Estado

```bash
bash scripts/status.sh
```

## Uninstall

```bash
bash scripts/uninstall.sh
```

Por ahora remueve los assets instalados en `~/.config/opencode/` y deja intacto el estado machine-local de runtime.
