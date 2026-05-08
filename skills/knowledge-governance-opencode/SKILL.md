# Skill: knowledge-governance-opencode

## Qué hago
- Defino cómo convivien Engram y Qdrant dentro del stack de OpenCode sin mezclar contratos.
- Ayudo a decidir qué información debe persistirse como memoria curada y qué material debe ir a un corpus recuperable.
- Refuerzo gobernanza de lectura/escritura, scopes, colecciones y metadata para el knowledge layer.

## Cuándo usarme
- Antes de escribir en Qdrant.
- Cuando hay dudas entre guardar algo en Engram o indexarlo para retrieval.
- Cuando un proyecto quiere especializar el knowledge layer global con corpus o metadata propia.
- Cuando hay que revisar si un agente debería leer o escribir dentro del knowledge layer.

## Reglas / checklist
- **Engram** para decisiones, preferencias, restricciones, learnings y resúmenes durables.
- **Qdrant** para corpus grande, regenerable y recuperable por similitud semántica.
- La escritura a Qdrant debe pasar por wrappers/scripts determinísticos aprobados; no por acceso directo libre.
- La lectura puede ser más amplia, pero siempre tratando los hits como evidencia recuperada y no como verdad absoluta.
- Mantener scopes separados: por ejemplo `global` para stack reusable y luego scopes/proyectos específicos sobre esa base.
- Preferir colecciones separadas por scope o propósito antes que mezclar corpus heterogéneo sin metadata suficiente.
- No persistir secretos, `.env*`, credenciales, dumps sensibles ni contenido `<private>...</private>`.
- Si el material es chico, altamente curado y durable, probablemente debería ir a Engram y no a Qdrant.
- Mantener el lifecycle por componente explícito: Engram y Qdrant deben poder instalarse, validarse y eventualmente extraerse por separado aunque convivan en un mismo repo umbrella.

## Salida esperada
- decisión explícita Engram vs Qdrant,
- scope / colección recomendados,
- metadata mínima sugerida,
- política de lectura/escritura aplicable,
- riesgos de ruido, duplicados o drift.
