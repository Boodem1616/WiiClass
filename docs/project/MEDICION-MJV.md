# Medición de uso e impacto de WiiClass (método MJV)

Este documento explica **qué KPIs se definieron, cómo se registran los datos y
en qué periodo se recolectaron**, tal como quedó en el código y en los datos
del proyecto.

> **Cómo leer este documento.** Cada afirmación está marcada por su origen:
> **[código]** está implementado y se puede comprobar en el repositorio;
> **[dato]** sale del archivo de datos que acompaña al proyecto;
> **[interpretación]** es una lectura razonable, pero no está escrita en el
> repositorio; **[COMPLETAR]** es información que el repositorio no contiene y
> debe aportar el equipo. En particular, el repositorio **no documenta** qué
> pasos formales tiene el método MJV más allá de lo que cita el código (§1), ni
> contiene un estudio con usuarios reales (§4).

---

## 1. El método MJV tal como aparece en el proyecto

El analizador (`tools/analyze_analytics.py`) declara que sigue el método MJV en
cuatro pasos **[código]**:

```
eventos crudos  →  métricas descriptivas  →  KPIs  →  análisis de embudo
```

| Paso | Qué responde | Dónde está |
|---|---|---|
| 1. Eventos crudos | Qué hizo el usuario, cuándo y en qué contexto | `wiiclass/services/analytics.py` (`registrar`) |
| 2. Métricas descriptivas | Qué está pasando | `contar_eventos`, `total_pantallas_visitadas`, `pantallas_mas_visitadas`, `resumen_sesiones` |
| 3. KPIs | Si se logra lo que importa al proyecto | `kpis()` |
| 4. Embudo | Dónde abandona el usuario | `embudo()` |

El código y los docs también se refieren a esta etapa como "Sesión 25" y
usan términos de clase ("anatomía" del evento, "desafío de lógica"), por lo que
el método proviene del material del curso **[código]**. **[COMPLETAR]:** nombre
oficial del método y fuente (curso, guía o autor) para citarla.

---

## 2. KPIs elegidos

### 2.1 KPIs (paso 3)

Definidos en `kpis()` con el comentario "alineados al éxito del proyecto"
**[código]**:

| KPI | Fórmula (según el código) | Qué indica |
|---|---|---|
| **Tasa de login exitoso** | `login_exitoso / (login_exitoso + login_error)` | Si el acceso funciona o se vuelve una barrera |
| **Clases abiertas que se reproducen** | clases distintas con `reproduccion_play` **manual** (`origen: manual`) ∩ clases distintas con `clase_abierta`, dividido por las clases distintas abiertas | Si quien entra a una clase toca play. No se cuenta el play `auto` que genera la app al abrirla |
| **Clases distintas escuchadas** | cantidad de `grabacion_id` distintos en `reproduccion_play` manual | Amplitud del uso del contenido |
| **Tasa de descarga exitosa** | `descarga_completa / (descarga_completa + descarga_error)` | Si el uso sin conexión es confiable |
| **Grabaciones guardadas** | conteo de `grabacion_guardada` | Uso de la función del Profesor |

**Por qué estos** **[interpretación]**: el problema que plantea el proyecto es
que el estudiante no alcanza a seguir la clase y tomar apuntes a la vez, y la
solución es grabar, escuchar después (incluso sin conexión) y que el profesor
pueda grabar. Cada KPI mide una pieza de esa cadena: acceder (login), escuchar
(reproducción), repasar offline (descargas) y producir contenido (grabaciones).
**[COMPLETAR]:** si el equipo definió metas o umbrales (por ejemplo "≥ 90 % de
descargas exitosas"), anotarlos aquí; el código no define metas, salvo la del
embudo.

### 2.2 Métricas descriptivas (paso 2)

Complementan a los KPIs **[código]**: total de pantallas visitadas, pantallas
más visitadas, eventos por tipo, número de sesiones, días con uso, sesiones por
día y duración promedio de sesión.

### 2.3 Embudo (paso 4)

Para el **Estudiante**, el embudo mide en cuántas sesiones se llega a cada
paso, **en orden** **[código]**:

1. Sesión iniciada (`login_exitoso` o `sesion_restaurada`)
2. Abre una categoría (`categoria_abierta`)
3. Abre una clase (`clase_abierta`)
4. Reproduce la clase (`reproduccion_play` con `origen: manual`; el play automático no cuenta)

El reporte marca una alerta si entre dos pasos se pierde **80 % o más** de las
sesiones (`UMBRAL_CAIDA_ALERTA = 0.80`). Es el único umbral definido en el
código. No hay un embudo equivalente para el Profesor.

---

## 3. Cómo se registraron los datos

### 3.1 Instrumentación **[código]**

Cada interacción relevante llama a `analytics.registrar(nombre, datos)`. Un
evento tiene esta forma:

```json
{ "evento": "login_exitoso", "ts": 1793805846.83, "sesion": "18e02e80",
  "rol": "Estudiante", "datos": { "metodo": "email" } }
```

- **Qué** (`evento`), **cuándo** (`ts`, segundos Unix) y **contexto** (`datos`,
  `rol`).
- `sesion`: un identificador de 8 caracteres generado **por cada apertura de la
  app**.
- `rol` se agrega solo si hay sesión iniciada, para separar Estudiante de
  Profesor.

Catálogo de eventos (19), definido en un único lugar para evitar errores de
tipeo: `app_iniciada`, `app_cerrada`, `pantalla_vista`, `login_exitoso`,
`login_error`, `sesion_restaurada`, `logout`, `categoria_abierta`,
`clase_abierta`, `reproduccion_play`, `reproduccion_pausa`,
`velocidad_cambiada`, `descarga_iniciada`, `descarga_completa`,
`descarga_error`, `grabacion_iniciada`, `grabacion_guardada`,
`notificacion_descartada`, `notificaciones_limpiadas`. Dónde se dispara cada uno
está en [`../technical/ANALITICAS.md`](../technical/ANALITICAS.md).

### 3.2 Almacenamiento **[código]**

- **Local**, en `datos/analytics.json` (en Android, dentro de la carpeta privada
  de la app). Se puede cambiar con la variable `WIICLASS_ANALYTICS_FILE`.
- **No se envía a ningún servidor**: el módulo no hace ninguna conexión de red.
  Recolectar datos de otros dispositivos requiere copiar el archivo (§5).
- Escritura **atómica** (archivo temporal + reemplazo) y agrupada (~1 s tras el
  último evento); se fuerza al cerrar la app.
- Máximo **5 000 eventos**: al superarlo se descartan los más antiguos.
- Medir **nunca rompe la app**: ante un fallo de disco o JSON corrupto, solo se
  escribe en el log.

### 3.3 Privacidad **[código]**

No se guardan contraseñas, correos ni nombres de personas: solo ids, nombres de
pantallas o categorías y el rol. El login registra únicamente el motivo del
fallo (`sin_institucion`, `campos_vacios`, `credenciales_incorrectas`), nunca
lo que se escribió. Tampoco hay un identificador de usuario, así que **no es
posible distinguir usuarios distintos ni medir retención** (ver §6).

### 3.4 Análisis **[código]**

```bash
python3 tools/analyze_analytics.py [ruta/al/archivo.json]
```

Calcula las métricas, los KPIs y el embudo a partir del JSON. No requiere Kivy.
Está cubierto por `tests/test_analytics.py`.

---

## 4. Periodo y datos recolectados

### 4.1 Lo que contiene el proyecto **[dato]**

El proyecto incluye un único archivo de datos, copiado aquí como
[`analytics_muestra.json`](analytics_muestra.json):

| Característica | Valor |
|---|---|
| Eventos | 22 |
| Sesiones (aperturas de la app) | **1** (`18e02e80`) |
| Fecha | **4 de noviembre de 2026** |
| Inicio – fin | 12:23:57 – 12:25:35 (hora de Chile, UTC−3); 15:23:57 – 15:25:35 UTC |
| Duración | ≈ 98 segundos (1 min 37 s) |
| Plataforma | Linux (escritorio) |
| Rol | Estudiante |
| Actividad | login → inicio → perfil → alertas (descarta 2 y limpia 8 notificaciones) → cierra sesión → vuelve a entrar → recorre pestañas → cierra la app |

### 4.2 Qué significa esto

**Esta muestra es una sesión de prueba de ~98 segundos, no un periodo de
recolección con usuarios.** No hay clases abiertas, reproducciones, descargas
ni grabaciones en ella, y por eso varios KPIs salen "sin datos". Es coherente
con una verificación de la función de notificaciones, no con un estudio de uso
**[interpretación]**.

Por lo tanto, el repositorio **no permite afirmar** un periodo de recolección
de días o semanas, ni un número de participantes. **[COMPLETAR]**, si hubo una
recolección real:

| Dato | Valor |
|---|---|
| Fecha de inicio y fin del periodo | |
| Participantes (cantidad y perfil: estudiantes / profesores, curso) | |
| Dispositivos / plataforma (Android, escritorio) | |
| Cómo se obtuvieron los archivos de cada dispositivo | |
| Cantidad de sesiones y eventos totales | |

### 4.3 Resultado del análisis sobre la muestra disponible

Salida real de `python3 tools/analyze_analytics.py docs/project/analytics_muestra.json`:

| Métrica / KPI | Resultado |
|---|---|
| Eventos / pantallas visitadas | 22 / 14 |
| Pantallas más visitadas | `home_tab` 5 · `notifications_tab` 4 · `profile_tab` 3 · `login` 2 |
| Sesiones · días con uso · duración promedio | 1 · 1 · 1 min 37 s |
| Login exitoso | **100 %** (2 de 2) |
| Clases abiertas que se reproducen | sin datos (no se abrió ninguna) |
| Clases distintas escuchadas | 0 |
| Descargas exitosas | sin datos |
| Grabaciones guardadas | 0 |

Embudo (Estudiante): sesión iniciada **1** → abre categoría **0** → abre clase
**0** → reproduce **0**. El reporte muestra "⚠ caída fuerte" en el paso 2, pero
es un artefacto de la muestra: en esta sesión de prueba nadie entró a una
categoría. **No debe leerse como un hallazgo de usabilidad.**

---

## 5. Cómo repetir la medición

1. Usar la app normalmente: los eventos se registran solos.
2. Copiar `datos/analytics.json` de cada dispositivo:
   - **Escritorio:** carpeta `datos/` de la raíz del proyecto.
   - **Android:** carpeta privada de la app (`<ANDROID_PRIVATE>/datos/`). En un
     APK de depuración puede extraerse con `adb`, por ejemplo:
     `adb exec-out run-as org.wiiclass.wiiclass cat files/app/datos/analytics.json > analytics_dispositivo1.json`
     (ruta sujeta a la versión de Android; verificar en el equipo).
3. Analizar cada archivo con `tools/analyze_analytics.py`. El analizador lee un
   archivo por vez; para consolidar varios dispositivos hay que unir antes las
   listas de eventos (cada `sesion` es distinta, así que no se mezclan).
4. Registrar en §4.2 el periodo, los participantes y los dispositivos.

---

## 6. Limitaciones

- **Mide uso, no impacto.** Los KPIs describen comportamiento dentro de la app
  (acceder, escuchar, descargar, grabar). Ninguno mide el efecto sobre el
  aprendizaje (notas, comprensión, tiempo ahorrado, satisfacción). Para hablar
  de impacto hace falta evidencia adicional, por ejemplo una encuesta o una
  comparación antes/después. **[COMPLETAR]** si el equipo la tiene.
- **Sin identificador de usuario** (por privacidad): no hay usuarios únicos,
  retención ni uso repetido por persona; solo sesiones.
- **La "sesión" es una apertura de la app**; su duración es el tiempo entre el
  primer y el último evento, no el tiempo de atención real.
- **Clases reproducidas** se calcula sobre el conjunto de clases distintas de
  todo el archivo, no por persona.
- **Solo cuenta el play manual.** La app inicia la reproducción sola al abrir una
  clase (`origen: auto`) y ese evento se excluye del KPI y del embudo. Quien
  escucha la clase completa sin tocar nada tampoco queda contado, y no hay un
  evento de progreso o finalización que mida cuánto se escuchó realmente.
- **Datos locales y por dispositivo:** nada se centraliza solo; el tope de 5 000
  eventos descarta los más antiguos en usos prolongados.
- **Sin metas definidas** (salvo el 80 % del embudo): sin un umbral por KPI no
  se puede declarar éxito o fracaso.
