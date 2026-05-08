# Instalación del addon knowledge

## Requisitos

- `opencode` ya instalado
- una instalación base funcional de OpenCode
- para Engram: `git`, `curl`, `tar` y Go o bootstrap automático de Go en Linux x86_64
- para Qdrant local: `python3` con soporte `venv`

## Instalación recomendada

```bash
git clone https://github.com/juanma91m/super-turing-opencode-knowledge.git
cd super-turing-opencode-knowledge
bash scripts/install.sh --all
```

## Modos por componente

### Solo Engram

```bash
bash scripts/install.sh --engram-only
```

### Solo Qdrant

```bash
bash scripts/install.sh --qdrant-only
```

### Solo assets, sin bootstrap runtime

```bash
bash scripts/install.sh --assets-only
```

## Qué instala

- assets del knowledge layer en `~/.config/opencode/`
- si se pide runtime Engram:
  - `~/.opencode/bin/engram`
  - checkout gestionado de Engram para build/patch
- si se pide runtime Qdrant:
  - `~/.local/share/super-turing-opencode-knowledge/`
  - virtualenv local con `qdrant-client[fastembed]`

## Validación

```bash
bash scripts/status.sh
```

Y por componente:

```bash
bash ~/.config/opencode/scripts/knowledge_status_engram.sh
bash ~/.config/opencode/scripts/knowledge_status_qdrant.sh
```

## Desinstalación

```bash
bash scripts/uninstall.sh
```

Importante: por ahora la desinstalación remueve solo los assets instalados en `~/.config/opencode/`. El estado runtime/local de Engram y Qdrant queda intacto para evitar borrados destructivos por defecto.
