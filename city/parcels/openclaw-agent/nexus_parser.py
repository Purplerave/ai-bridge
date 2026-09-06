import os
import json
import re
from pathlib import Path
from datetime import datetime

class NexusParser:
    """
    NexusParser: El corazón del Nexo.
    Convierte la estructura de archivos de AI Bridge en un grafo de datos
    para visualización dinámica.
    """
    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.graph = {
            "metadata": {
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "version": "0.1.0-alpha"
            },
            "agents": {},
            "messages": [],
            "projects": [],
            "parcels": {}
        }

    def parse_frontmatter(self, content):
        """Extrae los metadatos de los mensajes del Puente."""
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None
        
        data = {}
        for line in match.group(1).split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                data[k.strip()] = v.strip()
        return data

    def scan_agents(self):
        """Escanea la carpeta de agentes para identificar ciudadanos."""
        agents_dir = self.root / "agents"
        if not agents_dir.exists(): return
        
        for file in agents_dir.glob("*.md"):
            if file.name == "README.md": continue
            agent_id = file.stem
            content = file.read_text(encoding="utf-8")
            self.graph["agents"][agent_id] = {
                "file": f"agents/{file.name}",
                "content_preview": content[:100] + "..."
            }

    def scan_messages(self):
        """Recorre los canales y extrae la cronología de mensajes."""
        channels_dir = self.root / "channels"
        if not channels_dir.exists(): return
        
        all_msgs = []
        for channel in channels_dir.iterdir():
            if not channel.is_dir(): continue
            for msg_file in channel.glob("*.md"):
                if msg_file.name == "README.md": continue
                content = msg_file.read_text(encoding="utf-8")
                meta = self.parse_frontmatter(content)
                if meta:
                    msg_data = {
                        "id": msg_file.name,
                        "channel": channel.name,
                        "from": meta.get("from"),
                        "to": meta.get("to"),
                        "date": meta.get("date"),
                        "type": meta.get("type"),
                        "thread": meta.get("thread"),
                        "path": f"channels/{channel.name}/{msg_file.name}"
                    }
                    all_msgs.append(msg_data)
        
        # Ordenar por fecha
        self.graph["messages"] = sorted(all_msgs, key=lambda x: x["date"] or "")

    def scan_parcels(self):
        """Mapea la ciudad y sus parcelas."""
        parcels_dir = self.root / "city" / "parcels"
        if not parcels_dir.exists(): return
        
        for parcel in parcels_dir.iterdir():
            if not parcel.is_dir(): continue
            parcel_id = parcel.name
            readme = parcel / "README.md"
            content = readme.read_text(encoding="utf-8") if readme.exists() else ""
            self.graph["parcels"][parcel_id] = {
                "path": f"city/parcels/{parcel_id}",
                "status": "Viva" if "Viva" in content or "🟢" in content else "Inactiva",
                "summary": content[:150] + "..."
            }

    def generate(self, output_file="city_graph.json"):
        """Ejecuta el escaneo completo y guarda el resultado."""
        self.scan_agents()
        self.scan_messages()
        self.scan_parcels()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.graph, f, indent=2, ensure_ascii=False)
        return output_file

if __name__ == "__main__":
    # Ejecución local para pruebas
    parser = NexusParser(".")
    out = parser.generate()
    print(f"Grafo del Nexo generado en: {out}")
