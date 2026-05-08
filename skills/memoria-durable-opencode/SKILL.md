---
name: memoria-durable-opencode
description: Define como usar memoria durable en OpenCode sin acoplar la política a un backend específico.
compatibility: opencode
---
## Cuando usarme
- Cuando hay tools `mem_*` disponibles y conviene recuperar contexto previo antes de trabajar.
- Cuando una decision, discovery, bugfix, preferencia o patron merece memoria durable.
- Cuando una memoria vieja quedo obsoleta y hay que actualizarla o purgarla.

## Buckets canonicos
- `mem-global-user`: preferencias globales del usuario.
- `mem-global-engineering`: criterios tecnicos reutilizables cross-stack.
- `mem-tech-<stack>`: memoria reutilizable por tecnologia, por ejemplo `mem-tech-react`, `mem-tech-vaadin`, `mem-tech-spring-boot`.
- `<repo-canonico>`: memoria especifica del proyecto.

## Campos obligatorios
- `project`
- `scope`
- `type`
- `topic_key` (salvo `session_summary`)
- `source_agent`

## Source agent
- Guardar siempre `source_agent`.
- Convencion: persistirlo como `agent:<source_agent>`.
- Priorizar memorias de agentes afines, pero nunca como filtro excluyente si el contenido mas util viene de otro agente.

## Naturaleza de la memoria durable
- Tratar la memoria durable como working memory entre sesiones, no como auditoria completa ni historial detallado de iteraciones.
- Si una tarea necesita trazabilidad fuerte, intercambio por git o artefactos revisables por humanos, complementar con archivos del proyecto o documentacion local.
- No usar el backend de memoria durable como corpus grande de retrieval: si el stack tiene un knowledge layer con Qdrant u otro retrieval backend, esa capa queda para material amplio y regenerable; la memoria durable sigue siendo curada.
- Esta skill cubre **politica de uso** (qué guardar, cómo leer, cómo promover o purgar). Los detalles runtime/backend del proveedor concreto de memoria pertenecen a su addon o capa operativa específica.

## Lectura en dos pasos
- Para contexto reciente: `mem_context` primero.
- Para busquedas tematicas: `mem_search` primero para ubicar candidatos.
- Si un resultado importa de verdad, hacer siempre `mem_get_observation` antes de razonar o decidir sobre el contenido completo.
- No tomar decisiones importantes basadas solo en previews truncados de `mem_search`.

## Recuperacion en tres bloques
- Cuando haya memoria util, recuperarla en este orden:
  1. **Perfil usuario**: preferencias estables, estilo de trabajo, restricciones cross-proyecto.
  2. **Conocimiento proyecto**: arquitectura, stack, comandos, entry points, convenciones y gotchas del repo actual.
  3. **Memorias relevantes**: hallazgos que matchean con la tarea puntual en curso.
- No mezclar indiscriminadamente los tres bloques en un solo blob si eso pierde trazabilidad o mete ruido.
- Si no hay memoria curada del proyecto actual, considerar un bootstrap explicito (por ejemplo `/memory-init`) antes de forzar inferencias.

## Roles de lectura y escritura
- `master-dev` debe ser, por defecto, el lector principal de memoria y pasar a subagentes solo el contexto ya destilado cuando eso alcance.
- Los subagentes deben escribir discoveries, decisions y bugfixes relevantes cuando ocurran en su trabajo.
- Los subagentes solo deberian buscar memoria por cuenta propia cuando el historial especializado probablemente aporte valor real o cuando trabajan de forma mas autonoma sobre una fase concreta.

## Convencion para workflows largos
- Si un flujo es multi-fase o necesita recuperacion, usar nombres deterministas para sus artefactos y estado.
- Formato recomendado: `workflow/<nombre>/<artifacto>` o una familia equivalente del dominio.
- Guardar el estado y los artefactos largos con `topic_key` estable para permitir reanudacion limpia y evitar duplicados.

## Calibracion por fase de trabajo
- **Analisis / planning**: si la sesion solo deja preguntas o hipotesis temporales, no guardar memoria. Si confirma un descarte importante, una restriccion funcional, una regla de negocio no obvia o un hecho arquitectonico reusable, guardar **una** `decision` o `discovery` con `topic_key` estable.
- **Implementacion**: guardar `bugfix`, `decision`, `architecture` o `pattern` cuando el cambio deje una leccion durable. Si el tema evoluciona en varias iteraciones, preferir actualizar el mismo `topic_key` antes que crear memorias paralelas.
- **Validacion / testing**: guardar solo hallazgos tecnicos durables (`discovery`, `bugfix`, `pattern`) o una `session_summary` final cuando la validacion ya quedo cerrada. Evitar una `session_summary` nueva por cada rerun intermedio si la final ya sintetiza el estado.

## Topic keys recomendados
- Para analisis de tickets: `analysis/<ticket>/<tema>`
- Para validacion de tickets: `validation/<ticket>/<tema>`
- Para arquitectura o workflows evolutivos: `architecture/<tema-estable>` o `workflow/<nombre>/<artifacto>`
- Si una memoria nueva reemplaza claramente a otra del mismo tema, conservar el `topic_key` y actualizar la vigente en vez de abrir otra rama paralela.

## Que guardar
- Solo memoria durable, no obvia, reusable o valiosa entre sesiones.
- Preferencias estables del usuario.
- Decisions, architecture, pattern, learning, bugfix, constraint, integration, config.
- Session summaries solo como continuidad, no como reemplazo de memoria importante explicita.

## Que no guardar
- Prompts crudos.
- Logs o outputs de tools.
- Hipotesis temporales.
- Tareas triviales.
- Ruido conversacional.

## Convencion de privacidad
- Cualquier contenido envuelto en `<private>...</private>` debe tratarse como no persistible.
- Antes de guardar memoria, omitir o redactar esos fragmentos en vez de copiarlos literal.
- Si todo el contenido util de un hallazgo es privado, no guardarlo.

## Promocion
- Si algo nace en un proyecto y tambien sirve fuera de el, guarda el caso local en el proyecto y una version abstraida en el bucket reusable correcto.
- Quita detalles innecesarios del repo al promover a `mem-tech-*` o `mem-global-engineering`.

## Purga e higiene
- Si un tema evoluciona, primero actualiza o registra la memoria vigente.
- Luego purga la memoria obsoleta con soft-delete por defecto.
- Hard-delete solo para ruido puro, duplicados accidentales, datos sensibles o memorias incorrectas sin valor historico.
- Si hay varias memorias del mismo ticket/fase y solo la ultima sigue siendo operativamente util, conservar la mas vigente y evaluar soft-delete de las supersedidas.

## Señales de calibracion
- **Demasiado agresivo**: muchas `session_summary` del mismo ticket/fase, memorias que solo repiten output de validacion, o varias memorias paralelas para un mismo tema evolutivo sin `topic_key` comun.
- **Demasiado conservador**: sesiones de analisis que confirman descartes/restricciones importantes y no dejan ninguna `decision` ni `discovery`, o fixes/validaciones que enseñan algo reusable y no se persisten.
- **Acertado**: cada ticket relevante deja pocas memorias pero utiles, con hallazgos durables separados de summaries finales y con poco drift entre memorias viejas y vigentes.

## Bootstrap de lectura
- Siempre consultar primero `mem-global-user` y el proyecto actual cuando haya probabilidad real de contexto previo util.
- Luego consultar 1 a 3 buckets tecnicos relevantes a la tarea.
- No cargar toda la memoria global indiscriminadamente.
- Si `master-dev` ya recupero y sintetizo el contexto necesario, evitar que cada subagente repita las mismas busquedas salvo que haya una razon clara.

## Bootstrap de escritura inicial
- Cuando un repo aun no tiene memoria curada, crear una baseline chica y util:
  - comandos importantes,
  - stack y entry points,
  - restricciones fuertes,
  - arquitectura esencial,
  - gotchas reales.
- Evitar convertir el bootstrap en una auditoria exhaustiva; priorizar lo que ahorre tiempo en sesiones futuras.

## Orden de precedencia
1. Instruccion explicita actual del usuario.
2. Memoria del proyecto actual.
3. Preferencias globales del usuario.
4. Memoria reusable del stack.
5. Memoria global de ingenieria.
