# OSINT Engine Institucional

Aplicación de escritorio en **Flet** para organizar investigaciones OSINT basadas en **fuentes públicas**, con evidencia trazable y una integración directa y reproducible con **Maigret 0.6.5**.

> **Versión 0.2.0:** el alcance operativo se concentra en tres tipos de objetivo: **usuario**, **nombre** y **teléfono**. Maigret se ejecuta únicamente en el modo Usuario. Nombre y Teléfono permanecen como investigaciones independientes y no generan alias ni se envían a Maigret.

## Qué hace esta versión

- tres modos claros de entrada: Usuario, Nombre y Teléfono;
- Maigret como motor principal y único motor externo habilitado;
- el modo Usuario acepta `jose.gomez`, `@jose.gomez` o `jose.gomez@dominio.com`;
- cuando se pega un correo en el campo Usuario, se consulta **sólo** `jose.gomez`;
- Maigret consulta por defecto los **500 sitios** de mayor ranking de su base incluida;
- resultados de Maigret listados dentro de la aplicación;
- apertura directa del perfil público encontrado;
- imagen de perfil cuando Maigret logra extraer una URL de imagen;
- metadatos enriquecidos conservados como evidencia técnica;
- cancelación sin perder resultados ya obtenidos cuando la API instalada lo permite;
- exportación del expediente en JSON, CSV y GraphML;
- exportación adicional del **reporte HTML generado por el propio Maigret**;
- loader de inicio que prepara realmente la base de Maigret antes de habilitar la búsqueda;
- build Windows en un solo EXE mediante PyInstaller.

## Separación de modos

### Usuario — Maigret

Es el flujo funcional principal. La entrada se normaliza antes de llamar a Maigret. No se generan variantes desde nombres ni teléfonos y no se confunde una coincidencia de alias con identidad demostrada.

Ejemplos equivalentes:

```text
jose.gomez
@jose.gomez
jose.gomez@afasasda.com
```

Los tres terminan consultando:

```text
jose.gomez
```

### Nombre

Se registra como un objetivo independiente. En v0.2 no se transforma automáticamente en usernames ni se manda a Maigret. Esto evita producir ruido o presentar hipótesis débiles como resultados.

### Teléfono

Se normaliza y registra como un objetivo independiente. En v0.2 no se consulta con Maigret, ya que Maigret es un motor de usernames. La arquitectura queda preparada para incorporar después un adaptador específico para teléfono sin mezclar evidencias.

## Uso responsable

El sistema está diseñado para organizar información públicamente accesible. No elude autenticación, no realiza recuperación de contraseñas, no almacena credenciales y no incorpora técnicas de acceso no autorizado.

Una coincidencia de username prueba que ese alias fue detectado por Maigret en un servicio concreto; **no prueba por sí sola que todos los perfiles encontrados pertenezcan a una misma persona**.

## Instalación rápida en Windows / VS Code

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[desktop]"
python app\main_flet.py
```

También puede usar:

```powershell
.\scripts\run.ps1
```

## Pruebas

```powershell
python -m pip install --group dev
pytest
```

La suite incluye un smoke test contra la API Python instalada de Maigret para detectar incompatibilidades de integración.

## Empaquetar EXE

```powershell
.\scripts\build.ps1
```

El script instala dependencias, ejecuta pruebas, empaqueta y calcula SHA-256. El ejecutable queda en:

```text
dist\OSINT_Engine.exe
```

`OsintEngine.spec` incluye los módulos, plantillas y recursos de Maigret necesarios para que el reporte y la base de sitios también estén disponibles en el ejecutable.

## Exportaciones

Por defecto se guardan en:

```text
%USERPROFILE%\Documents\OSINT_Engine\exports
```

Para una investigación por usuario se generan:

```text
osint_<caso>.json
osint_<caso>.csv
osint_<caso>.graphml
maigret_<caso>.html
```

El último archivo es el reporte HTML nativo de Maigret construido a partir de los resultados de la ejecución actual.

## Estructura

```text
app/                      Interfaz Flet
src/osint_engine/
  adapters/               Integración con motores externos
  engine.py               Orquestación de investigación
  models.py               Modelos de hallazgo/evidencia
  normalization.py        Normalización de objetivos
  correlation.py          Dedupl./confianza conservadora
  exporters.py            JSON, CSV, GraphML y reporte Maigret
  security.py             Redacción para auditoría/UI
tests/                    Pruebas unitarias e integración ligera
docs/                     Arquitectura, seguridad y terceros
scripts/                  Ejecución y build reproducible
OsintEngine.spec          PyInstaller Windows
```

No suba resultados reales al repositorio.
