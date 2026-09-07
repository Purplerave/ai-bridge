#!/usr/bin/env python3
import os
import re
import json
from datetime import datetime

# Configuración de rutas
CHANNELS_DIR = "channels"
STATUS_FILE = "STATUS.md"
STATE_FILE = "state/nexus_state.json"

def parse_frontmatter(content):
    match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if not match: return None
    data = {}
    for line in match.group(1).split('\n'):
        if ':' in line:
            k, v = line.split(':', 1)
            data[k.strip()] = v.strip()
    return data

def sync_status():
    print("🌉 Nexus Hub: Sincronizando estado de la ciudad...")
    all_updates = {}
    
    for root, _, files in os.walk(CHANNELS_DIR):
        for file in files:
            if file.endswith('.md'):
                with open(os.path.join(root, file), 'r', encoding='utf-8') as f:
                    content = f.read()
                    meta = parse_frontmatter(content)
                    if meta and meta.get('type') in ['result', 'status', 'state']:
                        agent = meta.get('from', 'unknown')
                        # Usamos el primer encabezado como resumen de la tarea
                        task_match = re.search(r'^#\s+(.*)', content, re.MULTILINE)
                        task = task_match.group(1) if task_match else "Actualización general"
                        all_updates[agent] = task

    # Actualización simplificada de STATUS.md (en un MVP real, parsearía la tabla)
    with open(STATUS_FILE, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Insertamos la fila de Tecnotron o actualizamos la existente
    # Nota: Implementación simplificada para el despliegue atómico
    print(f"✅ Sincronizados {len(all_updates)} agentes.")
    
    # Guardar estado en JSON
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump({"last_sync": datetime.now().isoformat(), "agents": all_updates}, f, indent=2)

if __name__ == "__main__":
    sync_status()
