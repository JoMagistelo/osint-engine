# Setup

## Requisitos

- Windows 10/11 o Windows Server para validación de escritorio.
- Python 3.12 o 3.13.
- Git y VS Code opcionales para desarrollo.

## Instalación

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[desktop]"
python app\main_flet.py
```

La primera ejecución de Maigret necesita conectividad a Internet para consultar fuentes públicas. La aplicación no requiere claves API para el motor Maigret básico.
