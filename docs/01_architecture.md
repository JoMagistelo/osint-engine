# Arquitectura

```text
Identificadores del caso
        |
        v
Normalizer / Validator
        |
        v
InvestigationEngine
        |
        +--> MaigretAdapter ------> perfiles públicos
        |
        +--> SpiderFootAdapter ---> deshabilitado v0.1
        |
        v
Finding normalizado
        |
        +--> deduplicación / confianza
        +--> red de vínculos
        +--> evidencia
        +--> JSON / CSV / GraphML
```

Los adaptadores no deciden identidad. Producen hallazgos con procedencia. La correlación posterior conserva la diferencia entre dato observado e hipótesis.
