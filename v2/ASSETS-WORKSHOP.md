# Knowledge V2 — assets y wrappers para el workshop

## Estado

**Candidato general posterior:** `v2/general.mjs` y `general-assets.py` aportan
agentes/reglas nativos y wrappers canónicos sin depender de workshop-guard. Se
validaron con el candidato compuesto en fixtures; no se desplegaron al perfil
activo. Entorno local seleccionado se mantiene opaco y sólo se carga por la vía
runtime aprobada; configuración compartida instala el entorno canónico, no un
dispatcher autorreferente. El dispatcher legacy conserva su rechazo de igualdad
por defecto. Ver `opencode-stack/v2/general/COMPOSED.md` para evidencia y límites.

La composición está implementada y probada con fixtures. **El operador ya la
aplicó al workshop** y se verificaron config, permisos, MCP y login V2 presente.
Las capturas del operador confirmaron estado y consulta semántica del Qdrant real
desde V2, con el reader y proveedor real, sobre el corpus global existente.
Se mantiene el criterio del usuario: mismos backends, datos, configuración y
capacidades de Knowledge; sólo se adapta su integración con OpenCode V2.

El perfil compuesto contiene los once agentes base más `plan`, `build`,
`knowledge-reader` y `knowledge-curator` (**15 agentes**), las quince skills base
más tres de Knowledge (**18 skills**), cinco comandos y siete entradas de helper.
Plan/build siguen las plantillas guaranteed del addon, sin duplicar claves YAML.
El default master-dev, login del piloto V2, app/index, atajos y CLI/libnotify se
conservan. No se despliega nada en la configuración global V1.

### Recuperación del chequeo posterior a apply

El primer apply del operador terminó con `(intermediate value) is not iterable`:
los assets y el marker ya estaban aplicados; falló sólo su verificación posterior.
La causa no fue el reinicio de la PC. `/api/config` devuelve `Config.Entry[]`
directamente, mientras `/api/agent` y otros listados usan `{ location, data }`.
El launcher descartaba el array al leer siempre `.data`.

El stack ahora usa `getApiList`, que acepta ambas formas y valida arrays sin
exponer cuerpos de respuesta. `knowledge-inspect.mjs` comparte el chequeo completo
entre launcher y smoke, incluida config e integraciones: el smoke anterior sólo
cubría un subconjunto. La regresión nativa reprodujo primero el mismo TypeError;
corregida, incluye un control negativo del decoder viejo. Los agentes se esperan
con `until`: servidor HTTP listo no implica registros de plugins ya cargados.

`knowledge.mjs verify` pasó sobre el workshop ya aplicado: 15 agentes, 18 skills,
cinco comandos, Engram y Context7 conectados, conexión OpenAI existente y libnotify
configurado. No se repitió apply ni se ejecutó inferencia o indexación. Se compararon
hashes de config, instrucciones, CLI, binding, marker, app e índice antes/después
de verify. Para continuar basta `knowledge.mjs chat`; no reinstalar ni reconstruir.

## Contrato de los assets

- `assets.py` es un renderer **sin escrituras**: desde fuentes canónicas produce
  un plan JSON de archivos y bytes. No lee bases, auth stores ni `.env*`, no
  importa Qdrant y no ejecuta instaladores, embeddings o indexación.
- Se incluyen agentes, cinco comandos, tres árboles completos de skills con sus
  recursos (también binarios), playbooks, manifest de seed y contrato del broker.
  Recursos symlink se rechazan, no se siguen ni se omiten silenciosamente.
- La autonomía reutiliza el render canónico. Conserva cuerpo ajeno y reglas
  explícitas del caller, incluido un deny al reader. No duplica la regla que las
  plantillas plan/build ya contienen. El reader conserva los cinco mutadores
  denegados; curator conserva sus wrappers y prohibición de shell general.
- `composition.mjs` adapta esos assets al perfil sin absorberlos en la base. El
  stack sólo aporta el punto de extensión y el mecanismo de actualización.
- `upgradeOwned` valida el lote entero antes de reemplazar archivos individuales,
  compara bytes y rechaza drift/symlinks. Conserva `.pre-context7.bak` y usa
  `.pre-knowledge.bak` para este incremento. Cada reemplazo es atómico; **no es una
  transacción de filesystem completa** ante un error de I/O posterior.

## Reutilización de runtime: no inventar otro Qdrant

Los shims del perfil despachan a los wrappers **ya existentes** en el config-dir
del runtime seleccionado. Por lo tanto se conserva:

- `knowledge_env.local.sh` y sus overrides, sin copiarlo ni sourcearlo al preparar;
- el venv, modelo/backend de embeddings, rutas y colección actuales;
- el lock/flock de los wrappers originales;
- argumentos literales y source-root/manifest originales del seed;
- lectura vs escritura según el rol. No hay MCP Qdrant ni otro cliente vectorial.

`runtime.py` restaura HOME/XDG del runtime seleccionado, no los del HOME sintético
de V2. El binding sólo admite claves de configuración conocidas, sin tokens ni
URLs con credenciales. Se descartan password del servidor V2, keys de proveedor y
preloads de intérpretes; no se serializan credenciales. Los overrides locales
siguen siendo configuración confiable del runtime que se carga al ejecutar sus
wrappers, no datos nuevos para el modelo.

La excepción de implementación es status Engram: se ejecuta una copia de la
implementación canónica compatible con `.mcp.engram` V1 y `.mcp.servers.engram`
V2, inspeccionando el config-dir del perfil. El status agregado llama a sus dos
siblings del perfil. `engram_mcp_enabled=yes` significa **configurado/habilitado**,
no prueba conexión ni consulta; el launcher comprueba la conexión por API nativa.

La frontera del workshop valida shell literal mediante el parser del broker
canónico, sin ejecutar los helpers durante la validación. Sólo acepta shims
declarados y `helper knowledge-search|knowledge-status` para el planner. Conserva
los pins de scripts/bindings y las reglas nativas de actor/sesión; no permite
composición shell ni usar la nueva ruta para evitar un deny. No amplía shell
general, ediciones de aplicación o acceso remoto a negocio.

## Selección del wiring actual

`selected-runtime.py` lee sólo la definición Engram de un config V1 explícito y
exporta una selección validada, sin imprimir configuraciones ajenas. Conserva
argv, cwd original del piloto global, HOME, settings no secretos, autosync y
efectos globales de las once herramientas. No agrega `--project`, modo lector,
tools ni filtros nuevos. Wiring con secretos, interpolaciones no resueltas,
filtro distinto o overrides inline MCP de agentes se detiene para reconciliarlo,
en lugar de copiar credenciales o normalizar permisos silenciosamente.

La preparación de esta máquina (`knowledge.mjs plan`) confirmó que el Engram
actual está habilitado, usa el ejecutable existente y el filtro canónico de once
tools. Sólo se mostró metadata; **no se arrancaron esos backends ni se modificó
el workshop como efecto de plan**.

Este es tooling de migración del perfil global sintético, no el instalador final
ni un runtime manager. En el corte se deberá componer el layout nativo de assets
del addon; no apuntar un dispatcher a sí mismo ni abrir storage convertido con V1.

## Pruebas

La prueba nativa `smoke-knowledge.mjs` cubre ahora **24 casos**:

- los trece casos Engram previos, con el ejecutable actual y SQLite temporal;
- reader search/status, diagnóstico Engram sobre config V2 y planner vía broker;
- curator inventory/store/seed, siempre sobre un intérprete Qdrant ficticio;
- reader store denegado, override de sesión denegado e intento de shell injection;
- `/knowledge-search` nativo selecciona al reader, sin mutadores en su catálogo.

Se comprobó carga nativa de 15 agentes, 18 skills y cinco comandos; el endpoint
de comandos devuelve **204** al admitir la ejecución, no 200. Se verificaron
HOME/modelo/argv/source-root y que staging no consultara ni indexara corpus. El
test cierra sólo sus procesos y elimina únicamente su directorio temporal.
`debug config --standalone` verificó las fuentes aisladas. Las pruebas unitarias
cubren idempotencia, drift previo a cualquier cambio de agentes/helpers, backups,
bytes binarios, recursos completos, overrides y limpieza de entorno.

### Prueba humana de lectura confirmada

El operador ejecutó `/knowledge-status --qdrant-only` y `/knowledge-search` desde
el chat V2. Sus capturas muestran:

- Ejecución del shim del perfil y `status: ok` sobre el storage original, no uno
  creado bajo el HOME sintético; colecciones existentes disponibles.
- Embeddings mediante Ollama, `snowflake-arctic-embed2:latest`, dimensión 1024:
  se conservaron el runtime y los overrides actuales.
- Cinco hits en `global-opencode-knowledge` mediante el wrapper de búsqueda,
  con scope global/proyecto opencode-stack y fuentes del corpus existente.
- Uso de `engram_mem_doctor` y `engram_mem_search` en el mismo flujo de lectura;
  el diagnóstico mostrado no informa bloqueos para el proyecto consultado.

La búsqueda cubre la recuperación semántica extremo a extremo **de esa colección
y consulta**, no la consistencia de todas las colecciones, la calidad de todos los
hits ni la vigencia de sus documentos históricos. Los extractos recuperados no
reemplazan contratos actuales ni autorizan reintroducir funcionalidades descartadas.
Las capturas no muestran comandos de seed/store; no hizo falta reinstalar para
obtener el resultado de consulta mostrado.

El reporte de Engram informa backlog histórico de metadata en un proyecto no
enrolled. No activar Cloud, reparar ni reconstruir sólo para eliminar ese warning.
La lectura directa del wrapper fue bloqueada por el sandbox del piloto; `--help`
permitió consultar sus argumentos y el helper aprobado funcionó. No ampliar
permisos de archivos para sortear ese cierre temporal.

**No probado aún:** delegación nativa del reader, escrituras reales con contenido
durable genuino y cobertura de las demás colecciones/overlays. Las definiciones canónicas conservan
sus grants; la frontera temporal del workshop sigue cerrando delegación, como el
piloto anterior. No se declara equivalencia final por eso ni se elimina esa
capacidad del addon. Debe validarse antes del corte, junto con overlays pendientes.

## Incorporación y prueba del operador

Cerrar primero el cliente **del workshop V2**. No hace falta detener producción
V1 y este tooling no mata procesos del operador. Desde cualquier directorio:


Usá la entrada gestionada con el addon configurado; ver [Core](https://github.com/juanma91m/super-turing-opencode/blob/main/v2/install/README.md).


`--client-closed` es confirmación del operador, no detección ni aislamiento OS.
Apply es opt-in, preserva el storage/auth del piloto V2 y luego valida la config,
roles, catálogo, plugins y conexiones MCP. **A partir de apply se conecta al
Engram real con su comportamiento normal actual**, incluido autosync si estaba
configurado; no se cambia a un backend lector ni se prometen cero efectos internos.
No hace consultas a modelos, seeds o reindexaciones. Qdrant se abre cuando se
ejecuta un helper, con sus locks/cache/embeddings normales. Para futuras aperturas
de este perfil usar `knowledge.mjs chat|verify`, no el launcher base sin extensión.

En el chat probar, sin indexar ni guardar memorias de prueba:

```text
/knowledge-status --qdrant-only
/knowledge-search criterios de diseño de agentes OpenCode
```

Una búsqueda sin hits no prueba fallo: contrastar readiness, colección/modelo y
corpus existente. Después pedir una consulta acotada de Engram sobre la decisión
vigente de migración V2, indicando sólo lectura. No ejecutar `/memory-init`, seed
ni store para demostrar conexión. Escrituras y summaries ya están cubiertos por
fixtures; una validación real posterior debe corresponder a contenido durable
genuino, no basura de ensayo. Al guardar cambios de config se requiere reiniciar
el cliente; no asumir hot reload.
