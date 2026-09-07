# Estrategia de terceros

La arquitectura usa adaptadores para que un motor externo pueda actualizarse, deshabilitarse o sustituirse sin modificar modelos, interfaz o exportadores.

## Maigret

Se integra directamente mediante su API Python asíncrona y su base de sitios empaquetada. Se limita la concurrencia y se ofrece cancelación.

## SpiderFoot

No se vendorizan sus fuentes en esta versión. Antes de habilitarlo deben seleccionarse módulos permitidos, fijar la versión y validar su operación en Windows.

## Osintgram

No se incluye. Cualquier evaluación posterior deberá revisar tanto su licencia GPLv3 como la gestión de sesiones/credenciales y la estabilidad del mecanismo de acceso a Instagram.
