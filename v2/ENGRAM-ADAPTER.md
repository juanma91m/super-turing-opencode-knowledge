# Primer incremento V2: Engram y adaptadores de memoria

## Alcance implementado

Se adapta la integración con OpenCode V2 oficial 2.2.7, **sin cambiar el backend
Engram**, su esquema, su modo de apertura ni su política de datos. Este incremento
no es aún la composición completa de Knowledge en el workshop del operador.

- `engram-config.mjs` traduce una definición local V1 seleccionada explícitamente
  a MCP nativo V2, directo (`codemode:false`). Conserva argv, environment, cwd y
  estado enabled/disabled; no agrega flags, HOME, proyecto ni defaults de autosync.
- `engram-tools.json` fija las **11 herramientas actuales** y los **5 denies del
  reader**. El test Python contrasta ambos con las fuentes V1: drift exige revisión.
- La composición requiere efectos explícitos para las once herramientas. No
  sobreescribe servidores ni reglas/policies Engram existentes sin reconciliación.
  Conserva las demás entradas del perfil y los permisos específicos de cada agente.
- `plugins/engram/` registra mediante `@opencode/plugin` los ports de hints y
  asociación de summaries con el ID de sesión ejecutor. No agrega herramientas de
  memoria propias, permisos, procesos backend ni escrituras automáticas.
- `lib/memory-contract.mjs` comparte con los plugins V1 el texto/detección del
  hint y la inyección del ID. Los módulos auto-descubiertos V1 siguen exportando
  sólo factories. El manifest incluye el módulo compartido para no romper su
  instalación futura; **el refactor no se desplegó sobre V1**.

## Equivalencia de comportamiento

Los agentes autorizados siguen pudiendo guardar, resumir, actualizar, adjudicar y
usar review según sus reglas. No confundir `edit:deny` sobre archivos de aplicación
con prohibición de memoria: el planner y curator conservan persistencia. El reader
mantiene los cinco mutadores bloqueados, incluida `mem_review` completa. No se
expone `mem_delete`, se abren wildcards ni se habilita delegación para probarlo.

El hint mantiene el texto y patrón actuales, sin ampliar idiomas/keywords. V2
reconstruye su parte sintética en el contexto saliente a partir de registros
**user** y sus IDs; no reescribe el texto durable del usuario ni crea un turno
sintético adicional. No activa hints por contenido de attachments, herramientas
o mensajes synthetic. El API V2 distingue `SessionMessage.type/text` de mensajes
LLM `role/content`; no son estructuras intercambiables. La reconstrucción no
depende de un mapa volátil que se pierda al recargar el plugin. Se registra para
context, compaction y generate; la prueba nativa de este incremento cubre context,
no compaction/transient generation completos.

El ID se completa sólo en `engram_mem_session_summary` si no hay uno explícito y
no vacío. No se inyecta en `mem_save` ni se crean sesiones por otro mecanismo. El
upsert y la resolución de proyecto siguen siendo responsabilidad del backend.

## Pruebas realizadas

Desde este addon:

```bash
node --test v2/test/*.test.mjs tests/engram-session-context.test.ts
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/tmp/opencode OPENCODE_TEST_TMP=/tmp/opencode \
  python3 -m unittest discover -s tests -v
```

Desde el stack base canónico, con `/tmp/opencode` ya existente:

```bash
node --test migrations/v2/test/*.test.mjs
node migrations/v2/smoke-knowledge.mjs --engram-bin=/ruta/absoluta/al/engram-actual
node migrations/v2/smoke-context7.mjs
```

El smoke requiere seleccionar explícitamente un ejecutable existente. **No lo
instala, reconstruye ni reemplaza.** Usa el V2 oficial ya verificado, HOME/config/
data propios, SQLite temporal vacío precreado y autosync=0 sólo para el fixture.
Context7 es un fixture local coexistente; el proveedor de modelo es un mock HTTP
en loopback, no OAuth del operador ni inferencia real. El test elimina su propio
directorio temporal al terminar y cierra únicamente los procesos que creó.

Trece casos nativos pasaron: save master/planner/curator, summary con ID V2,
summary con ID explícito, reader read, reader deny, session override deny,
herramienta no expuesta, búsqueda que confirma que los intentos denegados no
persistieron, hint writer, hint reader sin grants adicionales y prompt sin hint.
Los dos casos summary guardan dos revisiones y abren la observación original para
verificar asociación con sesión y actualización de una sola observación.

Se ejecutó `opencode debug config --standalone` en el fixture y se verificaron
sus fuentes aisladas antes de arrancar el servidor privado. El catálogo ofrecido
al modelo coincide con los once tools, menos los denies del rol/sesión. No se
consultaron ni conectaron memorias reales al piloto. La regresión Context7 usó dos
llamadas documentales sintéticas y no reenvió los intentos privados/no autorizados.

## Pendiente antes de la prueba del operador

Estado histórico del primer incremento: la implementación de wrappers/assets y
composición listada abajo ya se completó en [el incremento siguiente](ASSETS-WORKSHOP.md).
Siguen pendientes su aplicación al perfil del operador y validación real; consultar
ese contrato actualizado, no usar esta lista como bloqueo de implementación.

- Wrappers Qdrant y sus rutas/modelo/configuración machine-local actuales, sin
  crear colecciones ni reindexar para migrar.
- Assets completos: agentes, skills/recursos, comandos, helpers del planner y
  autonomía aditiva, conservando capacidades y restricciones de cada rol.
- Composición gestionada del workshop preservando login, app/index, atajos y
  libnotify. No aplicar el installer V1 ni aceptar drift desconocido como baseline.
- Validación con backends actuales y prueba humana de la composición, sin
  confundir los resultados del modelo mock con obediencia de un proveedor real.

No hay todavía un comando nuevo de chat para el operador. La configuración real
del workshop no fue cambiada. Cuando se incorpore la composición, requerirá cerrar
y reiniciar ese cliente para cargarla; este hito por sí solo no exige reiniciarlo.

## Referencias de API verificadas

- https://opencode.ai/config.json
- https://opencode.ai/v2/docs/build/plugins/server
- https://opencode.ai/v2/docs/build/plugins/migrate-v1
- Tag `v2.2.7`: `packages/plugin/src/promise/{session,tool}.ts`,
  `packages/schema/src/session-message.ts`, `packages/ai/src/schema/messages.ts`.
