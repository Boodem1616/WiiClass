# Fundamentación UX/UI — WiiClass

> ⚠️ **Plantilla a completar con datos reales.** Este documento está
> estructurado exactamente según los subcriterios A1–A5 de la rúbrica
> (30 % de la nota de E2), pero los datos de investigación (número de
> entrevistas/encuestas, citas textuales, porcentajes) **no pueden
> generarse por IA**: deben salir de las entrevistas/encuestas que ya
> aplicaron a su socio comunitario/usuarios reales en el diagnóstico
> RA1. Cada sección marca con `[COMPLETAR]` lo que falta reemplazar.
> Si ya tienen ese análisis en la bitácora del lienzo de modelo de
> negocio de Taller de Emprendimiento, es cosa de traerlo aquí y
> conectarlo con las decisiones de interfaz concretas.

## a) Metodología de investigación (A1 — 5 pts)

- Instrumentos aplicados: `[COMPLETAR: ej. entrevista semiestructurada + encuesta cerrada]`
- Número de entrevistas: `[COMPLETAR]` — Número de encuestas: `[COMPLETAR]`
- A quiénes se aplicó (perfil, curso/carrera, cantidad): `[COMPLETAR]`
- Contexto / cómo se reclutó a los participantes: `[COMPLETAR]`

## b) Resultados principales, con evidencia (A2 — 10 pts)

Cada hallazgo necesita **evidencia verificable**: una cita textual de
entrevista, o un porcentaje/recuento de encuesta. Afirmaciones sin
respaldo ("a los usuarios les gustó la app") no puntúan según la
pauta.

| # | Hallazgo | Evidencia (cita textual o dato de encuesta) |
|---|---|---|
| 1 | `[COMPLETAR]` | `[COMPLETAR: "cita entre comillas" — Entrevistado X]` o `[N% respondió...]` |
| 2 | `[COMPLETAR]` | `[COMPLETAR]` |
| 3 | `[COMPLETAR]` | `[COMPLETAR]` |

## c) Matriz hallazgo → decisión de diseño (A3 — 10 pts)

Cada fila conecta un hallazgo específico con una decisión concreta de
interfaz (pantalla, jerarquía, texto, botón o flujo) ya implementada
en el código — no una intención genérica.

| Hallazgo (de la sección b) | Decisión de diseño tomada | Dónde está en la app |
|---|---|---|
| `[COMPLETAR]` | `[COMPLETAR: ej. "se agregó filtro por semana en Categoría"]` | `screens/category_screen.py` — pestañas de semana |
| `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` |
| `[COMPLETAR]` | `[COMPLETAR]` | `[COMPLETAR]` |

> Sugerencia: revisen las decisiones que YA está tomadas en el código
> (filtro por semana, descarga offline, selección múltiple, control de
> velocidad, notificaciones agrupadas) y trabajen hacia atrás — ¿cuál
> de estas respondió a qué hallazgo real de la investigación? Es más
> rápido que partir de cero, y es honesto: son decisiones que ya
> tomaron por alguna razón.

## d) Justificación de la estructura y navegación (A4 — 3 pts)

`[COMPLETAR: por qué estas pantallas, en este orden — Login → Inicio
(categorías) → Categoría (clases) → Reproductor —, y por qué esa
navegación responde al usuario real investigado y no solo a lo que
parecía razonable de diseñar.]`

## e) Diversidad y accesibilidad (A5 — 2 pts)

`[COMPLETAR: hallazgos de la investigación sobre diversidad de
usuarios — ej. poca familiaridad tecnológica, edad, condiciones de
conectividad distintas — y qué decisión CONCRETA de la interfaz
responde a cada uno. Ej.: si algún entrevistado mencionó poca
familiaridad con apps, ¿eso motivó botones más grandes, menos pasos,
textos más simples? Si nadie lo mencionó, es más honesto dejarlo
pendiente que inventar una consideración.]`

---

### Nota para quien complete esto

La pauta de corrección diferencia explícitamente entre "menciona la
investigación sin precisar instrumentos ni muestra" (parcial, 2,5 pts)
y "no presenta metodología" (0 pts) versus el logrado (5 pts) — el
nivel de detalle real importa más que la extensión del texto. Lo mismo
para los hallazgos: una cita textual corta vale más que un párrafo de
afirmaciones generales sin fuente.
