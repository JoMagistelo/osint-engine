# OSINT Engine Institucional

Aplicación de escritorio en **Flet** para organizar investigaciones OSINT basadas en **fuentes públicas**, con evidencia trazable, separación entre hechos e hipótesis y arquitectura de motores intercambiables.

> **Versión 0.1.0:** Maigret se integra como librería Python para búsquedas por usuario/alias. El adaptador SpiderFoot queda preparado pero deshabilitado hasta que se fije y audite un runtime compatible. Osintgram no se distribuye en esta versión.

## Alcance de la primera versión

- entrada por nombre, usuario/alias, correo y teléfono;
- normalización local de identificadores;
- búsqueda de perfiles públicos por usuario mediante Maigret;
- opción explícita para probar el texto local de un correo como **hipótesis** de alias, nunca como identidad confirmada;
- cancelación del análisis conservando resultados ya obtenidos;
- resultados con motor, URL, nivel de confianza y evidencia técnica;
- red visual de vínculos dentro de Flet;
- exportación JSON, CSV y GraphML;
- separación `app/`, `src/`, `tests/`, `docs/`, `scripts/`;
- build Windows con PyInstaller;
- procesamiento local y sin IA externa por defecto.

## Uso responsable e institucional

El sistema está diseñado para consultar información públicamente accesible y organizar evidencia. No debe utilizarse para eludir autenticación, ejecutar recuperación de contraseñas, almacenar credenciales personales, automatizar acceso no autorizado ni convertir coincidencias de alias en afirmaciones de identidad sin evidencia adicional.

La existencia de `@usuario` en varios servicios **no prueba** que todos los perfiles pertenezcan a la misma persona. La interfaz conserva esta distinción mediante estados y niveles de confianza.

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

## Ejecutar pruebas

```powershell
python -m pip install --group dev
pytest
```

## Empaquetar EXE

```powershell
python -m pip install -e ".[desktop]"
python -m pip install --group packaging
python -m PyInstaller --clean --noconfirm OsintEngine.spec
```

O:

```powershell
.\scripts\build.ps1
```

El resultado se genera en:

```text
dist\OSINT_Engine.exe
```

## Estructura

```text
app/                      Interfaz Flet
src/osint_engine/
  adapters/               Frontera con motores externos
  engine.py               Orquestación de investigación
  models.py               Modelos de hallazgo/evidencia
  normalization.py        Normalización de identificadores
  correlation.py          Dedupl./confianza conservadora
  exporters.py            JSON, CSV y GraphML
  security.py             Redacción para auditoría/UI
tests/                    Pruebas unitarias
docs/                     Arquitectura, seguridad y terceros
scripts/                  Ejecución y build reproducible
OsintEngine.spec          PyInstaller Windows
```

## Motores

### Maigret

Se usa como **librería Python**, no mediante scraping propio ni invocación opaca. En v0.1 se consulta un subconjunto de sitios de mayor ranking y se excluyen por defecto categorías `nsfw` y `dating`.

### SpiderFoot

Existe una frontera `SpiderFootAdapter`, pero no se incluye el runtime en v0.1. Esto permite auditar y fijar una versión antes de habilitar módulos específicos.

### Osintgram

No se empaqueta. Su modelo de autenticación y licencia requieren una revisión separada antes de cualquier integración institucional.

## Datos y exportaciones

La aplicación no persiste automáticamente una investigación. Sólo se escriben archivos cuando el operador pulsa **Exportar evidencia**. Por defecto se guardan en:

```text
%USERPROFILE%\Documents\OSINT_Engine\exports
```

No suba resultados reales al repositorio.
