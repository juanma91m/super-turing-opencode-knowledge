---
description: Bootstrap memoria durable del repo actual con hallazgos durables y curados.
agent: planner
subtask: false
---
Inicializá la memoria persistida del proyecto actual.

Objetivo:
- crear una baseline chica pero útil en el backend de memoria durable disponible para este repo,
- separar memoria de `perfil usuario`, `conocimiento proyecto` y `hallazgos relevantes`,
- guardar solo conocimiento durable, reusable y accionable,
- no implementar código ni tocar configuración salvo que el usuario lo pida aparte.

Proceso recomendado:
1. revisar si ya existe memoria relevante del proyecto y evitar duplicados,
2. inspeccionar README, manifests, build/test commands, entry points, stack, restricciones y docs clave del repo,
3. preguntar solo si falta una preferencia o regla crítica realmente útil para sesiones futuras,
4. guardar memorias chicas y separadas por tema usando `topic_key` estable,
5. resumir qué quedó sembrado y qué faltaría refinar.

Reglas:
- no guardar logs crudos, prompts enteros ni ruido conversacional,
- no persistir secretos ni contenido envuelto en `<private>...</private>`,
- priorizar decisiones, arquitectura, comandos importantes, convenciones, gotchas y restricciones,
- si ya existe memoria vigente del mismo tema, actualizar o reutilizar en vez de duplicar.

Formato esperado:
- `## Hallazgos sembrados`
- `## Hallazgos descartados`
- `## Próximos refinamientos opcionales`
