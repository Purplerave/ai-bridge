# Benchmark Multi-IA de Reparación Secuencial de Código (Code Repair)

Este módulo implementa el arnés de evaluación empírica y la suite de desafíos para medir la capacidad de reparación de código colaborativa e iterativa entre múltiples modelos e IAs.

## Estructura

```
research/code-repair/
├── harness.py              # Arnés CLI ejecutable para correr evaluaciones
├── README.md               # Especificación y documentación
├── benchmarks/             # Suite de desafíos con bugs deliberados y tests unitarios
│   ├── challenge_01_buggy_calculator/
│   ├── challenge_02_json_parser/
│   └── challenge_03_lru_cache/
├── results/                # Registros de resultados en formato JSON
└── tests/                  # Tests unitarios del arnés
```

## Uso del Arnés

Listar desafíos disponibles:
```bash
python3 research/code-repair/harness.py list
```

Ejecutar un desafío para un agente:
```bash
python3 research/code-repair/harness.py run --agent jules --challenge challenge_01_buggy_calculator
```

Ver estado general de los resultados:
```bash
python3 research/code-repair/harness.py status
```
