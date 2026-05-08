---
name: memoria-engram-opencode
description: Define como operar Engram como backend de memoria durable del addon knowledge.
compatibility: opencode
---
## Cuando usarme
- Cuando el stack ya decidió usar memoria durable y necesitás detalles específicos de Engram.
- Cuando necesitás revisar si el backend Engram está instalado, disponible o bien cableado.
- Cuando un cambio toca build, patch, binario, DB, MCP o status del componente Engram.

## Qué cubro
- contrato runtime del backend Engram,
- límites operativos de Engram,
- instalación, rebuild y status,
- relación entre Engram y el resto del knowledge layer.

## Qué NO cubro
- la política general de qué guardar, cómo clasificar memoria o cómo promover/purgar conocimiento durable,
- la decisión de memoria durable vs retrieval amplio,
- la gobernanza general del knowledge layer.

Para eso, usar primero:
- `memoria-durable-opencode`
- `knowledge-governance-opencode`

## Naturaleza de Engram
- Engram sigue siendo **working memory curada**, no corpus grande de retrieval.
- Si el material es amplio, regenerable o mejor apto para similitud semántica, corresponde más a Qdrant que a Engram.
- Las tools `mem_*` apuntan a Engram cuando el MCP local está habilitado en la configuración efectiva.

## Runtime actual esperado
- binario local: `~/.opencode/bin/engram`
- DB local: `~/.engram/engram.db`
- source checkout gestionado: `~/.local/src/engram-opencode-stack`

## Instalación / rebuild
```bash
bash ~/.config/opencode/scripts/install-knowledge-engram.sh
```

Wrapper legacy todavía soportado:
```bash
bash ~/.config/opencode/scripts/install-engram.sh
```

## Estado
```bash
bash ~/.config/opencode/scripts/knowledge_status_engram.sh
```

## Contrato con el stack base
- el stack base puede seguir teniendo política cognitiva de memoria y hints genéricos,
- pero el ownership de build, patch, binario, DB y wiring operativo de Engram pertenece al addon knowledge,
- si falta Engram, el stack base debería degradar con claridad y no asumir memoria persistente disponible.

## Señales de problema
- `engram_bin_present=no`
- `engram_mcp_enabled=no` cuando esperabas usar `mem_*`
- DB ausente o binario presente pero no cableado en config
- uso de Engram como si fuera corpus grande de retrieval
