# Seguridad

## Principios

- Sólo fuentes públicamente accesibles y motores expresamente habilitados.
- Sin recuperación de contraseñas ni pruebas de registro que generen efectos secundarios.
- Sin credenciales de redes sociales dentro del código, repositorio o artefacto.
- Sin envío de identificadores a modelos de IA externos por defecto.
- Sin persistencia automática de resultados.
- Logs de interfaz redactados para correo y teléfono.
- Una coincidencia de alias se trata como evidencia del alias, no como prueba concluyente de identidad.

## Datos personales

Los resultados pueden contener datos personales y perfiles públicos. Su tratamiento, retención, exportación, transferencia y acceso deben sujetarse a la finalidad institucional autorizada y a los controles aplicables de la organización.

## Secretos

No versionar `.env`, cookies, tokens, claves API, sesiones, contraseñas ni archivos reales de casos.

## Dependencias

Antes de una liberación institucional:

1. fijar versiones resueltas;
2. ejecutar auditoría de dependencias;
3. documentar procedencia y licencia de cada motor;
4. probar el EXE en un equipo Windows limpio;
5. generar hash SHA-256 del artefacto entregado.
