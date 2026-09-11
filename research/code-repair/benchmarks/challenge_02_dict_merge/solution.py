"""
Desafío 02: Combinación Profunda de Diccionarios (Deep Merge).

Función que combina dos diccionarios recursivamente.
"""

def deep_merge(dict_a, dict_b):
    result = dict(dict_a)
    for key, value in dict_b.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result
