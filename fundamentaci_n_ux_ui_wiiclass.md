# Fundamentación UX/UI — WiiClass

Este documento explicita la metodología de investigación aplicada al proyecto **WiiClass** y conecta cada hallazgo cuantitativo y cualitativo recopilado en el diagnóstico con las decisiones concretas de arquitectura de información e interfaz.

---

## a) Metodología de investigación (A1 — 5 pts)

- **Instrumentos aplicados:** Encuesta cuantitativa y cualitativa cerrada/abierta mediante formulario digital.
- **Número de entrevistas:** 0 entrevistas cualitativas individuales (la muestra investigada se basó en el instrumento de encuesta de campo).
- **Número de encuestas:** 16 respuestas completadas (16 participantes).
- **A quiénes se aplicó (perfil, curso/carrera, cantidad):** 16 estudiantes de la comunidad educativa asociada al socio comunitario WiiClass. El perfil corresponde a estudiantes expuestos a variaciones climáticas, problemas de conectividad a internet en sus hogares/comunidades y restricciones en dispositivos móviles.
- **Contexto / cómo se reclutó a los participantes:** Reclutamiento directo a través de los canales de comunicación y aula de la comunidad del socio comunitario. Las respuestas fueron recopiladas para evaluar el acceso a internet, la disponibilidad de almacenamiento en teléfonos y las preferencias de interfaz para el aprendizaje en modalidad híbrida/offline.

---

## b) Resultados principales, con evidencia (A2 — 10 pts)

| # | Hallazgo | Evidencia (cita textual o dato de encuesta) |
|---|---|---|
| 1 | **Alta vulnerabilidad de conectividad por condiciones climáticas y geográficas:** Más de la mitad de los usuarios sufre pérdida o inestabilidad de internet ante mal clima, e inasistencias forzadas. | El 37,5% (6/16) indica que *"Se corta la señal de internet, pero sí logro ir a clases"*, el 18,8% (3/16) *"Pierde la señal por completo y además se imposibilita viajar"* (56,3% afectado por clima). Además, un 18,8% (3/16) no cuenta con internet en su residencia. |
| 2 | **Restricción de almacenamiento móvil y demanda de gestión manual de descargas:** Un porcentaje significativo de usuarios maneja almacenamiento crítico y requiere control sobre qué descargar. | El 37,5% (6/16) presenta limitaciones de almacenamiento en su celular (18,8% borra fotos/apps con frecuencia y 18,8% casi nunca tiene espacio). Un 50,0% (8/16) prefiere *"Gestionar lo que se descarga"* frente a un 50,0% que prefiere descarga automática. |
| 3 | **Prioridad alta en seguimiento académico sin conexión y apoyo textual:** Necesidad crítica de sincronización offline de documentos y transcripciones. | El 81,2% (13/16) requiere *"Alertas de fechas de exámenes y entregas"*, el 81,2% (13/16) solicita *"Transcripción de las clases a texto"* y el 56,2% (9/16) requiere *"Acceso a material de lectura (PDFs) sin conexión"*. |
| 4 | **Preferencia por estructura compacta de 3 secciones principales:** La mayoría de los usuarios se inclina por una navegación simplificada. | El 62,5% (10/16) eligió la estructura de 3 pestañas: *"Biblioteca, Actividad, Descargas"*, seguido por un 25,0% (4/16) que prefirió *"Biblioteca, Descargas"*. |
| 5 | **Carga cognitiva reducida en notificaciones, tema visual y control de reproducción:** Búsqueda de eficiencia en reproducción y visualización nocturna/ahorro de energía. | El 93,8% (15/16) prefiere recibir notificaciones *"Solo cuando suban clases"*. El 56,2% (9/16) optó por *"Color Oscuro (azul, negro, violeta)"*. Citas cualitativas explícitas: *"Velocidad de reproducción del audio"* y *"Que esté catalogada cada clase"*. |

---

## c) Matriz hallazgo → decisión de diseño (A3 — 10 pts)

| Hallazgo (de la sección b) | Decisión de diseño tomada | Dónde está en la app |
|---|---|---|
| **Hallazgos 1 y 2:** 56,3% afectado por fallas de señal por clima, 37,5% con problemas de almacenamiento y 50% con preferencia de gestión manual. | Se diseñó la pestaña dedicada de **Descargas** con control manual e individual para descargar o eliminar audios y documentos PDF sin conexión, optimizando el uso de memoria. | `screens/downloads_screen.py` y botones de descarga local en `screens/category_screen.py`. |
| **Hallazgo 4:** 62,5% prefiere la combinación de navegación en 3 pestañas (*Biblioteca, Actividad, Descargas*). | Se implementó una barra de navegación inferior fija (`BottomNavigationBar`) restringida a las tres vistas solicitadas (*Biblioteca*, *Actividad*, *Descargas*), eliminando pestañas secundarias innecesarias. | `screens/home_screen.py` (componente principal de navegación). |
| **Hallazgos 3 y 5 (Comentario cualitativo):** Petición expresa de *"Velocidad de reproducción del audio"* y transcripción/reproducción pendiente. | Se integró un control de velocidad de reproducción configurable (0.5x, 1x, 1.25x, 1.5x, 2x) en el reproductor de clases, junto al guardado automático del punto de reproducción. | `screens/player_screen.py`. |
| **Hallazgos 3 y 5 (Comentario cualitativo):** Petición expresa de *"Que esté catalogada cada clase"*, 81,2% de alerta de exámenes y 93,8% de notificación al subir clases. | Se agrupó el contenido por asignaturas y semanas/categorías con tarjetas visuales claras, e integración de notificaciones push agrupadas sobre entregas y nuevas clases en *Actividad*. | `screens/category_screen.py` y `screens/activity_screen.py`. |
| **Hallazgo 5:** 56,2% de preferencia por tema de color oscuro y 62,5% por íconos regulares (10% de pantalla). | Se adoptó un tema visual en tono oscuro (Dark Mode predeterminado o seleccionable) para ahorrar batería y mitigar el cansancio visual, con área de contacto amplia en íconos estándar. | `theme/app_theme.py` e íconos universales de interfaz. |

---

## d) Justificación de la estructura y navegación (A4 — 3 pts)

La arquitectura de la información y el flujo de navegación de WiiClass (**Login → Inicio/Biblioteca → Categoría/Clases → Reproductor/Detalle**, complementados por la barra inferior fija con **Biblioteca**, **Actividad** y **Descargas**) responden directamente a la realidad de los usuarios investigados:

1. **Jerarquía orientada a la inmediatez:** La encuesta reveló que el 56,3% sufre interrupciones climáticas o de señal y un 37,5% ha considerado o piensa en dejar de estudiar debido a dificultades para ponerse al día. Por esta razón, al ingresar a la aplicación el usuario no encuentra promocionales ni páginas intermedias, sino la **Biblioteca de asignaturas** organizadas de forma clara y catalogada.
2. **Acceso directo a contenido offline (*Descargas*):** Colocar *Descargas* en la barra de navegación principal asegura que cuando el estudiante pierda la conexión en el trayecto o por mal clima, pueda acceder a sus clases almacenadas con un solo toque sin depender del servidor.
3. **Foco en el seguimiento (*Actividad*):** El 81,2% de los encuestados exige alertas de exámenes y entregas. La pestaña *Actividad* centraliza notificaciones e hitos pendientes en un formato cronológico simple, previniendo la sobrecarga de notificaciones no deseadas (el 93,8% pidió notificaciones enfocadas exclusivamente a contenido relevante).

---

## e) Diversidad y accesibilidad (A5 — 2 pts)

Las decisiones de diseño de interfaz responden a los perfiles de diversidad de usuarios identificados en la investigación:

- **Diversidad de conectividad y capacidad de hardware:** Con un 18,8% de estudiantes sin internet en el hogar y un 37,5% con teléfonos de espacio limitado o de gama de entrada, la aplicación evita animaciones pesadas y permite la **gestión manual e individual del almacenamiento**, dando control total sobre qué audios o PDFs mantener en el dispositivo.
- **Accesibilidad visual y ergonomía táctil:** El 56,2% eligió colores oscuros y el 62,5% solicitó íconos de tamaño regular (10% de la pantalla). Se implementó una paleta de alto contraste con modo oscuro que ahorra batería en zonas rurales sin luz estable, junto con blancos de toque (*touch targets*) holgados para facilitar la interacción de usuarios con poca familiaridad digital o en movimiento (ej. traslados en transporte rural).
- **Alternativas de consumo de contenido (Audio + Texto):** El 81,2% de preferencia por transcripciones de audio a texto respalda la inclusión de lectura accesible para estudiantes con dificultades auditivas, entornos ruidosos o quienes prefieren repasar material de forma visual sin consumir datos de audio.