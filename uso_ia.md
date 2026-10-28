# Declaración de uso de Inteligencia Artificial — WiiClass

Este documento declara cómo se usó inteligencia artificial (IA) en WiiClass, una maqueta funcional (Kivy + KivyMD 2.0) de una app móvil para grabar y descargar clases en audio.

---

## 1. IA usada

Se utilizó **Claude**, el asistente de IA de Anthropic, como herramienta de apoyo al desarrollo.

La IA participó en la mayor parte de los archivos del repositorio: código Python, archivos KV y documentación. Cada archivo indica en su encabezado que fue generado o asistido con IA, de modo que la participación se puede verificar directamente en el código.


## 2. Modelo

- **Modelo:** Claude (Anthropic), usado mediante su interfaz de chat.
- **Versión:** Sonet 5.5

## 3. Prompts realizados

Los prompts relevantes, resumidos con fidelidad, fueron de tres tipos:

| Tipo | Qué se pidió |
|---|---|
| Construcción de módulos | Generar la estructura de pantallas, la lógica y la interfaz de la app (login, inicio, categoría, reproductor, notificaciones, perfil, descargas), manteniendo la separación entre archivo `.py` (lógica) y `.kv` (interfaz). |
| Corrección de errores | Diagnosticar y corregir un problema de rendimiento: el chequeo de conectividad en el login bloqueaba el hilo principal y congelaba la interfaz. |
| Documentación | Redactar el `README.md` y el documento de fundamentación UX/UI a partir de los hallazgos de la investigación con usuarios hecha por el equipo. |

## 4. Outputs

| Output de la IA | Qué se tomó | Qué se descartó o corrigió |
|---|---|---|
| Código de módulos y pantallas | Estructura base y lógica de cada módulo | Lo que no funcionaba al ejecutar la app o no calzaba con los requisitos se corrigió en iteraciones posteriores |
| Corrección del login | Mover el chequeo de conectividad fuera del hilo principal (detalle técnico en `README2.md`) | El comportamiento anterior, que bloqueaba la interfaz |
| Textos de documentación | Redacción del README y de la fundamentación UX/UI | Afirmaciones que no coincidían con el estado real del proyecto |

## 5. Ajustes

Lo que el equipo definió, decidió y verificó por su cuenta:

- **Arquitectura y tecnologías:** se eligió Kivy + KivyMD con `MDScreenManager`, y la separación de cada pantalla en `.py` y `.kv`.
- **Problema y usuario:** el problema, el usuario objetivo y el diagnóstico con estudiantes de UC Temuco son del equipo. La IA redactó la fundamentación, pero a partir de esos hallazgos.
- **Alcance:** se delimitó qué queda dentro de la maqueta y qué fuera (autenticación real, servidor persistente, notificaciones push, configuración remota).
- **Roles y datos de ejemplo:** se definieron los roles Estudiante y Profesor, con barras de navegación distintas según rol, y los usuarios demo.
- **Funcionamiento sin dependencias opcionales:** se mantuvo un *fallback* a `kivy.core.audio` si `ffpyplayer` no está disponible, para que la app siempre se pueda ejecutar.
- **Verificación:** el equipo ejecutó la app, probó los flujos principales y documentó bugs y soluciones en `README2.md` y `REVISION-DISENO-Y-BUGS.md`.

La IA propuso y generó; el equipo ejecutó, probó, corrigió y decidió qué se incorporó al repositorio.

## 6. Reflexión en el uso de IA

La IA nos ayudó a avanzar mucho más rápido: generó la estructura inicial de las pantallas, resolvió un bug de rendimiento que no habíamos identificado y nos permitió redactar documentación ordenada. Lo que más nos costó fue confiar en el código sin entenderlo: algo que parece correcto puede fallar al ejecutarlo, así que tuvimos que probar todo y leerlo con atención. También notamos que la IA no conoce a nuestros usuarios, por lo que las decisiones de diseño y alcance tenían que salir de nuestra investigación y no de sus sugerencias.

Aprendimos que usar IA no reemplaza entender el proyecto: es más útil cuando uno sabe qué quiere pedir y es capaz de evaluar lo que recibe. También aprendimos a estructurar un projecto y ver las multiples parte que lo constitullen para realizarlo y  como la ia acelera el proceso pero no realiza todo el trabajo.