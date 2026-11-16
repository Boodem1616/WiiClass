# Fundamentación UX/UI — WiiClass

Este documento explica cómo la investigación con estudiantes llevó a las
decisiones de interfaz de WiiClass. Sigue los subcriterios A1–A5 de la rúbrica.

> **Origen de los datos.** Las cifras de la encuesta (16 respuestas) son las del
> diagnóstico del equipo, tal como están en
> [`fundamentaci_n_ux_ui_wiiclass.md`](fundamentaci_n_ux_ui_wiiclass.md). Las
> columnas "Dónde está en la app" fueron verificadas contra el código actual
> (`wiiclass/ui/...`). Donde un hallazgo **no** tiene una decisión
> implementada, se dice explícitamente (ver §c, "Hallazgos sin respuesta
> todavía").

## a) Metodología de investigación (A1 — 5 pts)

- **Instrumentos aplicados:** encuesta digital con preguntas cerradas
  (opción única o múltiple) y preguntas abiertas.
- **Número de entrevistas:** 0. No se hicieron entrevistas individuales; toda
  la evidencia sale de la encuesta.
- **Número de encuestas:** 16 respuestas completas (16 participantes).
- **A quiénes se aplicó:** 16 estudiantes de UC Temuco ligados al socio
  comunitario del proyecto. El perfil común es el de estudiantes que dependen
  de una conexión a internet irregular (en el hogar o en el trayecto) y de
  teléfonos con poco espacio libre.
- **Contexto / cómo se reclutó:** convocatoria directa por los canales de
  comunicación y el aula de la comunidad del socio. La encuesta preguntó por
  acceso a internet, almacenamiento del celular, preferencias de descarga,
  navegación, notificaciones, tema visual y funciones deseadas.
- **Límite del método:** 16 respuestas no permiten generalizar; sirven para
  priorizar decisiones de diseño, no para estimar porcentajes de toda la
  universidad.

## b) Resultados principales, con evidencia (A2 — 10 pts)

| # | Hallazgo | Evidencia (dato de encuesta o cita) |
|---|---|---|
| 1 | **La conectividad falla con frecuencia, sobre todo por clima.** Más de la mitad pierde o ve inestable la señal con mal tiempo. | 37,5 % (6/16): *"Se corta la señal de internet, pero sí logro ir a clases"*. 18,8 % (3/16): pierde la señal por completo y además no puede viajar. En total, 56,3 % afectado por clima. Además, 18,8 % (3/16) no tiene internet en su residencia. |
| 2 | **El almacenamiento del celular es limitado y quieren controlar qué se descarga.** | 37,5 % (6/16) tiene limitaciones de espacio (18,8 % borra fotos o apps con frecuencia; 18,8 % casi nunca tiene espacio). 50,0 % (8/16) prefiere *"Gestionar lo que se descarga"*; el otro 50,0 % prefiere descarga automática. |
| 3 | **Necesitan seguimiento académico con apoyo en texto y sin conexión.** | 81,2 % (13/16) pide alertas de fechas de exámenes y entregas; 81,2 % (13/16) pide transcripción de las clases a texto; 56,2 % (9/16) pide acceso a material de lectura (PDF) sin conexión. |
| 4 | **Prefieren una navegación compacta de 3 secciones.** | 62,5 % (10/16) eligió *"Biblioteca, Actividad, Descargas"*; 25,0 % (4/16) eligió *"Biblioteca, Descargas"*. |
| 5 | **Quieren pocas notificaciones y herramientas para escuchar mejor.** Piden un tema visual oscuro y respuestas abiertas piden más velocidad y orden. | 93,8 % (15/16) quiere notificaciones *"Solo cuando suban clases"*. 56,2 % (9/16) eligió color oscuro (azul, negro, violeta). Respuestas abiertas: *"Velocidad de reproducción del audio"* y *"Que esté catalogada cada clase"*. |

## c) Matriz hallazgo → decisión de diseño (A3 — 10 pts)

| Hallazgo (de la sección b) | Decisión de diseño tomada | Dónde está en la app |
|---|---|---|
| **1 y 2.** Conectividad inestable y poco espacio en el celular (56,3 % afectado por clima; 37,5 % con poco almacenamiento). | Pestaña **Descargas** para escuchar clases guardadas sin conexión. La descarga es manual (una clase o varias), el contenido se agrupa por asignatura como en Inicio y cada clase muestra su tamaño. El estado vacío explica qué hacer ("Descárgalas con el WiFi del campus…"). | `wiiclass/ui/screens/downloads_tab.py` y `.kv`; botón de descarga en `category_screen.py`; `services/downloads_manager.py` |
| **1.** Se corta la señal aun con clase presente. | Para el **Estudiante**, la pestaña Descargas aparece **solo cuando no hay conexión**, así el contenido guardado queda a un toque justo cuando hace falta. "Siguiente" en el reproductor salta solo entre clases descargadas si no hay red. | `main_screen.py` → `tabs_para_rol`; `player_screen.py` |
| **2.** 50 % quiere gestionar lo que se descarga. | **Selección múltiple**: mantener presionada una tarjeta activa el modo de selección para descargar varias clases juntas y decidir cuáles guardar en el teléfono. | `category_screen.py` (`activar_seleccion_multiple`) |
| **4.** 62,5 % prefiere una navegación de pocas secciones. | **Barra inferior fija** con 4 destinos para el Estudiante: Inicio (biblioteca de asignaturas), Descargas, Alertas (actividad) y Perfil. Las tres secciones elegidas en la encuesta (Biblioteca, Actividad, Descargas) existen como Inicio, Alertas y Descargas; Perfil se sumó para cerrar sesión. | `main_screen.py` → `tabs_para_rol` |
| **5.** Respuesta abierta *"Que esté catalogada cada clase"*. | Clases organizadas **por asignatura** (Inicio) y **por semana** (chips *Todas / Semana 1 / Semana 2…* dentro de cada categoría, calculados según las clases existentes). Cada tarjeta muestra fecha legible y duración. | `home_tab.py`, `category_screen.py` (`_construir_pestanas_semana`) |
| **5.** Respuesta abierta *"Velocidad de reproducción del audio"*. | **Control de velocidad** 0,5× / 1× / 1,5× / 2× en el reproductor (los valores se pueden cambiar por configuración remota), más saltos de −10 s y +10 s. | `player_screen.py`; configuración en `services/remote_config.py` |
| **5.** Pocas notificaciones. | Las alertas son **locales y de confirmación** (bienvenida, descarga completa, grabación guardada), sin mensajes promocionales; la pestaña Alertas muestra la lista y permite descartarlas o limpiarlas. | `services/notification_service.py`, `notifications_tab.py` |

### Hallazgos sin respuesta todavía

Para no atribuirle a la investigación decisiones que no existen:

- **Alertas de exámenes y entregas (81,2 %) y aviso solo cuando suban clases
  (93,8 %).** La app no tiene servidor, así que las notificaciones son locales
  y no avisan de clases nuevas ni de fechas.
- **Transcripción a texto (81,2 %) y PDF sin conexión (56,2 %).** No están
  implementados; hoy la app trabaja con audio.
- **Eliminar descargas para liberar espacio (hallazgo 2).** Hoy solo se
  puede descargar; no hay un botón para quitar una clase del teléfono.
- **Tema oscuro (56,2 %).** La interfaz actual es clara ("tinta azul sobre
  papel", `wiiclass/ui/theme.py`). No hay modo oscuro.

Son la base natural de una siguiente iteración.

## d) Justificación de la estructura y navegación (A4 — 3 pts)

El flujo **Login → Inicio (asignaturas) → Categoría (clases por semana) →
Reproductor** sigue la tarea que el estudiante describió: llegar rápido a una
clase concreta y escucharla, muchas veces con conexión mala.

1. **Del contenido general al específico, sin pantallas intermedias.** Tras el
   login el estudiante ve directamente sus asignaturas; elige una, filtra por
   semana y abre la clase. Es la jerarquía que pidió con *"que esté catalogada
   cada clase"*, y evita páginas sin utilidad cuando la red es lenta.
2. **Descargas en la barra principal.** Como el 56,3 % sufre cortes por clima
   y el 18,8 % no tiene internet en casa, el contenido guardado no puede estar
   escondido en un submenú: se muestra en la barra cuando no hay conexión.
3. **Pocas secciones.** El 62,5 % prefirió tres secciones. La barra se mantiene
   en cuatro destinos (el Profesor tiene además Grabación) y cada uno responde
   a una necesidad distinta: encontrar clases, repasar sin red, revisar avisos
   y administrar la sesión.
4. **El reproductor es el destino final.** Reúne lo que el estudiante pidió
   para estudiar con calma: velocidad, avance/retroceso de 10 s y barra de
   progreso.

## e) Diversidad y accesibilidad (A5 — 2 pts)

La encuesta mostró diversidad en **condiciones de acceso**, no en habilidades
digitales: ningún dato recogido habla de edad o de poca familiaridad con apps,
y por eso no se atribuye ninguna decisión a esos factores.

- **Conectividad desigual** (18,8 % sin internet en casa; 56,3 % afectado por
  clima). Decisión: modo sin conexión con descargas y pestaña Descargas
  prioritaria cuando no hay red.
- **Dispositivos con poco espacio** (37,5 %). Decisión: descarga manual,
  individual o múltiple, para que cada persona decida qué ocupa su memoria, y
  se muestra el peso de cada archivo. Borrar una descarga desde la app aún no
  existe (ver §c).
- **Diferentes formas de estudiar el audio.** Decisión: velocidad desde 0,5×
  (para entender mejor) hasta 2× (para repasar rápido).
- **Legibilidad.** Se usa un único azul de alto contraste sobre fondo claro,
  con texto principal oscuro (`theme.py`), botón de reproducir grande y
  tarjetas de altura fija (76 dp) para tocar con facilidad.
- **Pendiente:** la preferencia por modo oscuro (56,2 %) y la transcripción a
  texto (81,2 %), que beneficiaría a quien no puede escuchar en ese momento o
  tiene dificultades auditivas, no están implementadas (ver §c).
