# Declaración de uso de inteligencia artificial — WiiClass

**Herramienta:** Claude (Anthropic), como asistente de desarrollo y redacción.
**Equipo / curso:** Sebastián Flores (`Boodem1616`) y el colaborador `ChrisTheDarkss`,
autores de los commits del repositorio. Proyecto WiiClass,
UC Temuco, entrega E2 (diagnóstico UX/UI, prototipo y documentación).
**Versión del modelo y fechas de uso:** Claude (Anthropic). El repositorio no
registra la versión exacta del modelo. Fechas: según las fechas de los archivos
y del historial de git, la asistencia se concentró entre el 11 y el 15 de
noviembre de 2026 (revisión, reorganización y documentación); el proyecto se
desarrolló desde el 23 de septiembre de 2026.

## Qué es del equipo

El concepto de la app y el problema que resuelve, el diagnóstico con
estudiantes y sus hallazgos (ver [`../ux/`](../ux/)), las decisiones de
arquitectura (Kivy + KivyMD, `ScreenManager`, separación `.py` / `.kv`,
SQLite) y la implementación original de cada pantalla.

## Dónde se usó IA

Según lo registrado en este repositorio. El detalle técnico de cada punto está
en los documentos enlazados.

| Área | Uso de la IA | Detalle |
|---|---|---|
| Rendimiento | Diagnóstico y corrección del chequeo de conectividad que bloqueaba el hilo principal en el login (`is_online()`) | [`REVISION-DISENO-Y-BUGS.md`](REVISION-DISENO-Y-BUGS.md), [`../technical/IMPLEMENTACION.md`](../technical/IMPLEMENTACION.md) |
| Revisión de diseño y errores | Rediseño visual (paleta en `theme.py`, componentes en `common.kv`) y lista de bugs corregidos | [`REVISION-DISENO-Y-BUGS.md`](REVISION-DISENO-Y-BUGS.md) |
| Revisión de la entrega | Comentarios y sugerencias sobre la app en ejecución | [`COMENTARIOS-Y-SUGERENCIAS.md`](COMENTARIOS-Y-SUGERENCIAS.md) |
| Funcionalidades y su documentación | Descarga de audio y copia a Documentos, empaquetado con Buildozer, configuración remota, analíticas, notificaciones y persistencia | [`../technical/`](../technical/) |
| Documentación UX/UI | Redacción del documento de fundamentación a partir de los hallazgos del equipo | [`../ux/`](../ux/) |
| README | Redacción y actualización | [`../../README.md`](../../README.md) |
| Reorganización del proyecto | Traslado a la estructura `wiiclass/` (data, services, ui), actualización de imports, rutas, `buildozer.spec` y documentos, y verificación con tests y arranque de la app | [`../technical/IMPLEMENTACION.md`](../technical/IMPLEMENTACION.md#equivalencias-con-la-estructura-anterior) |

> **Nota:** la declaración que tenía el README antes de la
> reorganización mencionaba solo el bug de rendimiento y la redacción del
> README y de la fundamentación UX/UI. Los demás documentos del repositorio
> están redactados en primera persona por un asistente, así que esta tabla
> incluye también esos usos. Si algún punto no corresponde a lo que realmente
> se hizo, debe corregirse antes de entregar.

## Cómo se verificó el trabajo asistido

- Los tests del proyecto (117, sin Kivy) se ejecutan con
  `python3 -m unittest discover -s tests -t .`.
- Tras la reorganización se comprobó que la app arranca y navega con ambos
  roles. No se compiló el APK con Buildozer.
- La IA puede equivocarse: todo cambio generado debe ser revisado y probado por
  el equipo, que es responsable del resultado final.
