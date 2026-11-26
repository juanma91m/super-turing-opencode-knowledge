# Playbook: Knowledge Component — Engram

## Qué resuelve

- memoria curada y durable entre sesiones,
- decisiones, restricciones, preferencias y learnings de alta señal,
- continuidad semántica chica, no corpus grande.

## Cuándo usar Engram

- cuando algo debe **recordarse** entre sesiones,
- cuando el valor está en el resumen curado y no en el texto completo,
- cuando necesitás `topic_key`, promoción, actualización o purga.

## Qué NO usar Engram para

- corpus grande regenerable,
- documentación extensa pensada para búsqueda semántica,
- chunks numerosos o material recuperable mejor apto para Qdrant.

## Runtime actual

- binario local: `~/.opencode/bin/engram`
- DB local: `~/.engram/engram.db`
- source checkout gestionado: `~/.local/src/engram-opencode-stack`

## Base del build gestionado: Engram 3.7.2

El build del addon deriva de **[Engram v3.7.2][engram-372]**,
commit `c6ba9e3c0e98ffa0d5591481d8670a575e7b70b0`.
`KNOWLEDGE-MANIFEST.json` fija el archivo fuente, su SHA-256 y Go 1.26.11.
La etiqueta `3.7.2+opencode.1` distingue nuestro build del binario oficial.
El manifest describe el build, no la activación en cada máquina.
Confirmá la versión instalada y la que reporta el MCP tras reconectarlo.

Desde el checkout canónico del addon, construir sin acceso a la base
Engram (la descarga y Go sí pueden usar red):

```bash
bash scripts/build-engram-candidate.sh /ruta/privada/existente/engram-3.7.2-opencode.1
```

El build no sustituye archivos, no modifica el checkout anterior y
no abre la base. El parche nuevo conserva sólo `source_agent`
(codificado en `tool_name`), la clave histórica de los resúmenes
idempotentes y las instrucciones de memoria curada para el catálogo
de 11 herramientas. Un primer resumen con un ID `ses_…` suministrado
por OpenCode sólo puede vincularlo al proyecto detectado sin
ambigüedad; `mem_save` no obtiene esta excepción. Se conserva la
exigencia upstream de `expected_project` para `mem_update`: es
el dueño verificado de la observación, no un proyecto inferido o un
cambio de dueño.

Se aprovechan las mejoras upstream de búsqueda y del arranque SQLite,
y la redacción de bloques privados en `mem_judge`. No se habilitan Pi,
Cloud, daemon, autosync, organizaciones ni herramientas nuevas. No se
reaplican los parches históricos de diagnóstico Cloud o de escaneo
semántico; no hay cambio en los wrappers o despliegues Cloud.

Antes del corte: comprobar 11 herramientas y denies de OpenCode,
resumen que actualiza la misma observación, búsqueda/procedencia y
rechazo de proyecto incorrecto. Validar integridad y preservación de
datos en una copia SQLite consistente, sin red y con permisos privados.
Conservar una copia consistente del estado y el binario anteriores
para revertir juntos. No asumir que el binario viejo pueda abrir una
base que ya abrió la versión nueva.

Prueba de integración del candidato (base sintética, sin red, con `bwrap`):

```bash
ENGRAM_372_CANDIDATE_BIN=/ruta/privada/existente/engram-3.7.2-opencode.1 \
  python3 -B -m unittest discover -s tests -p test_engram_372_candidate.py -v
```

[engram-372]: https://github.com/Gentleman-Programming/engram/releases/tag/v3.7.2

## Instalación / rebuild

Los siguientes comandos son **legacy**: todavía construyen la base
anterior y no deben ejecutarse para reconstruir 3.7.2, ni sobre una
instalación que ya migró su base. Para 3.7.2 usá el builder de arriba
y tratá el reemplazo como un corte separado.

```bash
bash ~/.config/opencode/scripts/install-knowledge-engram.sh
```

Alias legacy todavía soportado:

```bash
bash ~/.config/opencode/scripts/install-engram.sh
```

## Estado

```bash
bash ~/.config/opencode/scripts/knowledge_status_engram.sh
```

## Superficie MCP y sesiones

- el wiring OpenCode del addon expone las tools de memoria más `mem_judge`,
  `mem_current_project`, `mem_doctor` y `mem_review`,
- `mem_delete` queda fuera de la superficie operativa por defecto,
- `mem_doctor` reutiliza el evaluador determinístico de Cloud repair: metadata
  legacy de proyectos enrolled bloquea; backlog de proyectos unenrolled queda
  como warning report-only con evidencia de secuencia/hash y sin payload crudo,
- el plugin `engram-session-context.ts` inyecta el `sessionID` real de OpenCode
  solo en `engram_mem_session_summary` y preserva cualquier ID explícito,
- si ese ID todavía no existe en SQLite, `mem_session_summary` resuelve el
  proyecto con las reglas normales y crea la sesión antes de guardar; esta
  excepción no relaja el rechazo de sesiones desconocidas en `mem_save`,
- cada summary con un ID canónico usa
  `topic_key=session/<session-id>/summary`: repetir una sesión actualiza la misma
  observación y otra sesión crea una distinta; IDs explícitos no canónicos usan
  un segmento hash estable para no colisionar al normalizar o truncar.

### Instrucciones según el registro efectivo

El patch del addon construye el catálogo de instrucciones con las herramientas
registradas después del filtro `--tools`, ordenadas de forma estable. El cliente
conserva el control de nombres, carga, descubrimiento y permisos por rol; el servidor
no promete disponibilidad universal ni prescribe una API de búsqueda del cliente.

Las reglas de uso son proporcionales: no releer contexto suficiente, guardar
hallazgos durables al estabilizar hitos y resumir sólo continuidad nueva. Los
pedidos explícitos y restricciones críticas no esperan a perderse; las lecturas
y cierres locales obligatorios se conservan. Un rol read-only no escribe y un rol
sin acceso pide contexto, sin CLI/SQL como bypass. La política completa está en
`memoria-durable-opencode`, no en un bootstrap fijo por varios buckets.

Con adjudicación se conserva el protocolo completo de conflictos;
sin ella, se informa la limitación y se dejan los juicios pendientes para un contexto
autorizado, sin CLI bypass ni falsas confirmaciones. Esto no cambia los filtros,
handlers, campos estructurados o anotaciones. Las descripciones de uso sí cambian
con la política; no son cambios de permisos. El template Claude puede
tener otro filtro: no asumir que coincide con OpenCode o con el cliente instalado.

Para validar metadatos de la línea anterior, los tests aceptan `ENGRAM_CANDIDATE_BIN` y,
opcionalmente, `ENGRAM_BASELINE_BIN`, ambos paths de builds aislados. Sin candidato
explícito, las pruebas nativas se omiten: nunca arrancan por defecto el binario
instalado. Sus fixtures aíslan HOME/cwd/datos, desactivan autosync y precrean un
SQLite vacío para evitar migración de bases huérfanas al iniciar. Solo usan
`initialize` y `tools/list`, no escrituras de memoria ni llamadas a modelos.

El patch necesita un rebuild autorizado para activarse. El instalador completo
también recompone el checkout gestionado: no ejecutarlo para probar un candidato
ni reemplazar el binario activo sin autorización y backup.

Para actualizar bloques de autonomía ya instalados, usar el render existente desde
las bases canónicas y contrastar el cuerpo efectivo: `apply` no sustituye un bloque
ya marcado. No tocar permisos ni otros bloques de addons para forzar esa actualización.

OpenCode trata **cada export** de un archivo auto-descubierto bajo `plugins/*.ts`
como una plugin factory. Esos módulos deben exportar únicamente factories que
devuelvan un objeto de hooks; helpers internos no deben llevar `export`.

`engram conflicts scan --semantic` puede ejecutar llamadas al runner también en
dry-run, pero sin `--apply` no persiste relaciones ni mutaciones de sync. Usar
`engram conflicts scan --help` para revisar flags y presupuesto antes de correrlo.

## Réplica Cloud opcional

Cada PC conserva SQLite local y puede sincronizar una allowlist explícita de
proyectos contra Engram Cloud:

```bash
~/.config/opencode/scripts/knowledge-push
~/.config/opencode/scripts/knowledge-pull
~/.config/opencode/scripts/knowledge-sync
~/.config/opencode/scripts/knowledge-sync-status
```

El servidor, bootstrap seguro y timer horario están documentados en
[`PLAYBOOK-KNOWLEDGE-CLOUD.md`](./PLAYBOOK-KNOWLEDGE-CLOUD.md).

## Contrato con el stack base

- el stack base sigue decidiendo **cuándo** consultar memoria,
- `memoria-durable-opencode` sigue modelando la política cognitiva,
- este componente resuelve el backend/runtime de Engram y su MCP.

## Boundary actual

Todo lo que sea build, patch, binario, DB y status de Engram vive ya en `super-turing-opencode-knowledge`.
La política genérica de memoria y el wiring MCP de compatibilidad siguen temporalmente en el stack base y se desacoplan después.
