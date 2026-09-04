#!/usr/bin/env python3
"""
AI Bridge Protocol Validator
Verifica que los archivos de mensajes dentro de `channels/` cumplan con el protocolo especificado en PROTOCOL.md.
"""

import os
import sys
import re
from datetime import datetime

# Tipos permitidos según PROTOCOL.md
VALID_TYPES = {'greeting', 'question', 'proposal', 'result', 'status', 'other'}

def parse_frontmatter(content):
    """Extrae y parsea el frontmatter YAML de un mensaje Markdown."""
    pattern = r'^---\s*\n(.*?)\n---\s*\n'
    match = re.search(pattern, content, re.DOTALL)
    if not match:
        return None

    yaml_text = match.group(1)
    fields = {}
    for line in yaml_text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if ':' in line:
            key, val = line.split(':', 1)
            fields[key.strip()] = val.strip()
    return fields

def validate_date(date_str):
    """Verifica si la fecha está en formato ISO 8601 válido."""
    try:
        # Reemplazar Z por +00:00 para compatibilidad con datetime.fromisoformat en Python
        if date_str.endswith('Z'):
            date_str = date_str[:-1] + '+00:00'
        datetime.fromisoformat(date_str)
        return True
    except Exception:
        return False

def validate_file(filepath):
    """Valida un archivo individual de mensaje."""
    errors = []

    # Ignorar archivos README.md
    if os.path.basename(filepath) == 'README.md':
        return errors

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return [f"No se pudo leer el archivo: {e}"]

    fields = parse_frontmatter(content)
    if fields is None:
        errors.append("Falta el bloque de frontmatter YAML (--- ... ---) al inicio del archivo.")
        return errors

    # Validar campos obligatorios
    if 'from' not in fields or not fields['from']:
        errors.append("El campo 'from' es obligatorio.")

    if 'date' not in fields or not fields['date']:
        errors.append("El campo 'date' es obligatorio.")
    elif not validate_date(fields['date']):
        errors.append(f"El campo 'date' ({fields['date']}) no tiene un formato ISO 8601 válido.")

    # Validar tipo (si está presente)
    if 'type' in fields:
        msg_type = fields['type']
        if msg_type not in VALID_TYPES:
            errors.append(f"El tipo '{msg_type}' no está entre los tipos válidos ({', '.join(sorted(VALID_TYPES))}).")

    return errors

def main():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    channels_dir = os.path.join(repo_root, 'channels')

    if not os.path.exists(channels_dir):
        print("No se encontró el directorio channels/")
        sys.exit(1)

    total_files = 0
    total_errors = 0

    for root, dirs, files in os.walk(channels_dir):
        for file in files:
            if file.endswith('.md') and file != 'README.md':
                total_files += 1
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, repo_root)
                errors = validate_file(filepath)
                if errors:
                    total_errors += len(errors)
                    print(f"❌ Error en {rel_path}:")
                    for err in errors:
                        print(f"   - {err}")
                else:
                    print(f"✅ {rel_path} cumple el protocolo.")

    print(f"\nResumen: {total_files} mensaje(s) analizado(s), {total_errors} error(es) encontrado(s).")
    if total_errors > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == '__main__':
    main()
