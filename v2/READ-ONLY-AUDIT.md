# Knowledge V2 — compatibilidad actual y auditoría de arranque

## Estado y alcance

Auditoría de integración, 2026-11-12. **No es un instalador ni una composición
V2 habilitada.** Producción, configuración global, binarios y bases reales quedan
intactos. No se copiaron bases, indexaron corpus ni conectaron los stores reales
al workshop. Esa auditoría inicial agregó documentación y tests sintéticos. El
[primer incremento Engram](ENGRAM-ADAPTER.md) posterior ya implementa adaptadores
y wiring, probados sólo contra fixtures; no es un despliegue sobre el operador.

Knowledge conserva el ownership de Engram, Qdrant, wrappers, adaptadores y tests.
La base coordina su incorporación incremental. No introducir un MCP Qdrant nuevo,
un proxy de memoria ni acceso SQL/CLI para eludir permisos de un rol.

**Aclaración del usuario, posterior a la auditoría:** Knowledge debe funcionar
tal y como funciona hoy, en su estado actual. La migración adapta la integración
con OpenCode V2, no rediseña los backends ni cambia sus garantías. Se descarta la
propuesta de un candidato Engram con un nuevo modo lector. Los efectos normales
de arranque descritos abajo son comportamiento existente, no un bloqueo ni un bug
que esta migración deba corregir. La primera prueba de consulta no implica
deshabilitar persistencia, autosync u otras capacidades legítimas de la capa final.

Hay tres garantías diferentes:

1. **Lectura del agente:** no puede guardar, resumir, actualizar, adjudicar,
   marcar reviews ni indexar. Es una política de herramientas/roles.
2. **Sin mutación persistente del backend:** el arranque tampoco migra, repara,
   crea storage ni sincroniza datos. Una allowlist lectora no demuestra esto.
3. **Sin efectos operativos:** locks, WAL/SHM, caches, descargas de modelos y red
   también deben considerarse. No prometer ausencia física de toda escritura sólo
   porque SQLite se abra con `mode=ro`.

La migración conserva las garantías actuales por rol, sin agregar las garantías
2 o 3 como requisito nuevo. No prometerlas tampoco. La desactivación de autosync
en los fixtures es aislamiento del test, no una modificación de la configuración
operativa que se debe trasladar.

## Evidencia del backend gestionado

### Engram

Fuente canónica del build: ref fijado por `scripts/install-knowledge-engram.sh`
(`1dafc0f63051b2214100f7bd801357e4aab61c26`) más
`patches/engram-source-agent.patch`. El checkout gestionado es un artefacto de
build, no el lugar para mantener una modificación permanente.

| Evidencia | Consecuencia |
|---|---|
| `cmd/engram/main.go`, `main`: `migrateOrphanedDB` precede al dispatch | Con destino inexistente puede mover una DB huérfana; exigir ruta explícita y DB existente no equivale a desactivar todo mantenimiento |
| `cmdMCP`: usa `storeNew`, no `storeNewReadOnly` | El filtro `--tools` no selecciona un modo de storage lector |
| `internal/store/store.go`, `New`: WAL, `migrate`, `repairEnrolledProjectSyncMutations` | Un proceso MCP lector conserva capacidad de modificar esquema/datos en el arranque |
| `cmdMCP`: `tryStartAutosync` antes del servidor MCP | Preservar la configuración operativa de autosync; desactivarlo sólo en fixtures aislados |
| `NewReadOnly` ya existe para diagnósticos | No cambiar el arranque MCP para usarla como parte de esta migración |

Prueba con el **binario instalado**, seleccionado explícitamente y ejecutado sólo
contra fixtures: `initialize` + `tools/list` con cinco herramientas lectoras
**cambian el storage SQLite temporal inicialmente vacío**. No se llamó a ninguna
herramienta de memoria. Esto verifica el límite de arranque del binario probado;
no implica que toda apertura de una DB ya inicializada vaya a modificarla.

El parser actual de `cmdMCP` no ofrece un modo lector explícito; no agregar un
supuesto `--read-only` a la configuración ni introducirlo como requisito nuevo.

### Scope no es una ACL

`MCPConfig.DefaultProject` / `--project` seleccionan el proyecto por defecto; no
son una frontera de autorización:

- `handleSearch` acepta un proyecto explícito diferente y `all_projects=true`;
- `scope=personal` sin override explícito consulta transversalmente;
- `handleGetObservation` obtiene por ID antes de resolver el envelope del
  proyecto; ese envelope no demuestra que la observación pertenezca al default.

Preservar la resolución y los alcances actuales, incluidas las consultas cruzadas
legítimas. No presentar el default como aislamiento entre proyectos ni imponer
una ACL nueva como efecto de la migración. Este hallazgo se verificó en fuente,
no mediante consultas cruzadas sobre memorias reales.

### Qdrant

Fuentes: `scripts/knowledge_env.sh`, `knowledge_search.sh`,
`knowledge_status_qdrant.sh` y `knowledge_store.py`.

- Los wrappers pueden sourcear `knowledge_env.local.sh`; no ejecutarlo para
  descubrir secretos/configuración de una máquina por intuición.
- Search/status crean el directorio del lock y toman `flock -x`.
- `make_client` crea el directorio de storage y abre `QdrantClient(path=...)`.
  Es Qdrant local file-based, no un daemon HTTP implícito.
- `command_status` también construye el embedder y calcula su dimensión. Con
  FastEmbed puede involucrar cache/descarga; con Ollama, una petición `/api/embed`.
  No es una simple inspección offline. Enumera colecciones, no sólo la seleccionada.
- Search usa `ensure_existing_collection`: falla si falta la colección, sin crear
  una. Aun así, ya abrió el cliente y construyó el embedder.
- Los filtros de search son opcionales: omitir `--scope` y `--project` no hereda
  los defaults de indexación. Preservar el routing y los filtros del flujo actual,
  sin estrechar o ampliar implícitamente su alcance al adaptar los wrappers.

Los tests nuevos usan dependencias falsas, storage temporal y payloads ficticios.
Verifican routing, fallos, filtros y ausencia de create/upsert/delete en una
consulta acotada. **No certifican el comportamiento físico del cliente Qdrant
real ni la disponibilidad del runtime/modelo instalado.**

## Diseño vigente del siguiente incremento

1. Reutilizar el backend Engram actual y el runtime Qdrant existente. No generar
   un nuevo build, patch, modo de apertura ni esquema de datos. No copiar bases,
   crear colecciones o reindexar como efecto del setup.
2. Adaptar el wiring MCP a V2 conservando la superficie operativa actual de
   `scripts/manage_opencode_config.py` y los permisos efectivos por rol. El reader
   sigue sin mutadores; los roles autorizados conservan persistencia, summaries,
   review y adjudicación. Una prueba inicial de lectura no recorta esa composición
   final ni autoriza herramientas nuevas.
3. Trasladar explícitamente las rutas y configuración machine-local necesarias
   para usar los mismos backends desde el HOME del piloto. Preservar autosync,
   modelo, colección y routing efectivos; no inferir defaults distintos ni copiar
   secretos a documentación o repositorios.
4. Incorporar Qdrant por los wrappers existentes y adaptar sólo lo necesario para
   V2. Conservar sus locks, embeddings y filtros normales. No inventar un servicio
   MCP ni reemplazar el mecanismo actual por un acceso alternativo.
5. Portar agentes, skills, comandos, autonomía y adaptadores de sesión/hints con
   equivalencia funcional. Preservar restricciones por rol y resolver diferencias
   reales del host V2 mediante APIs públicas; no cambiar la política de Knowledge
   para acomodar un fixture. La selección de delegación del host sigue siendo una
   decisión de la migración base, no una razón para perder capacidades de memoria.
6. Validar progresivamente catálogo, permisos, consulta, persistencia y sesiones.
   Preservar login, Context7, alertas, atajos y fixture del workshop. No declarar
   equivalencia completa por haber pasado únicamente una consulta lectora.

### Sesiones: puerta separada para escritura

`engram-session-context.ts` V1 sólo completa `session_id` ausente en summaries y
preserva un ID explícito. El backend distingue casos: `mem_session_summary`
puede crear la sesión faltante mediante su resolución normal; `mem_save` no
autoriza una sesión desconocida de la misma forma. Antes de portar el adaptador,
probar en fixtures el ID real de V2, resolución de proyecto, resumen idempotente,
IDs explícitos, sesiones distintas, errores y rol ejecutor. No asumir registro
automático universal ni abrir tools de gestión de sesiones como bypass.

## Validación reproducible

Desde la raíz del addon, con un directorio temporal aprobado ya existente:

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp/opencode OPENCODE_TEST_TMP=/tmp/opencode \
  python3 -m unittest discover -s tests -v
```

La caracterización del binario exige opt-in explícito. El nombre histórico
`ENGRAM_CANDIDATE_BIN` selecciona el ejecutable; **no lo instala ni reemplaza**.
Sus procesos reciben HOME/cwd/data temporales, un SQLite vacío precreado para
evitar búsqueda de huérfanas y entorno sin Cloud/proveedor heredados. Autosync=0;
sólo RPCs de metadata. No usar este fixture como prueba de acceso lector a la DB
real ni como receta para arrancar un MCP normal sobre ella.

```bash
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp/opencode OPENCODE_TEST_TMP=/tmp/opencode \
  ENGRAM_CANDIDATE_BIN=/ruta/absoluta/al/engram-seleccionado \
  python3 -m unittest discover -s tests -p test_opencode_integration.py -v
```

Resultado de la auditoría inicial: suite general 43 casos, **37 pasaron y 6 omitidos**;
suite de integración con binario explícito 13 casos, **10 pasaron y 3 omitidos**.
Omisiones: baseline comparativa, contrato Claude y permisos nativos V1 no
solicitados; el primer comando también omite pruebas que requieren binario.
No hubo inferencia ni consulta Qdrant/Engram real. `debug config` no aplica aún:
no se cambió ni habilitó configuración V2; se exigirá al componer el incremento.
