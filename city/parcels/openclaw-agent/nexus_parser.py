import argparse
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

# Raíz del repo deducida desde este archivo: city/parcels/openclaw-agent/ -> 3 arriba.
# Así el parser da el mismo grafo se ejecute desde donde se ejecute.
REPO_ROOT = Path(__file__).resolve().parents[3]
PARCEL_DIR = Path(__file__).resolve().parent

# Destinos canónicos del grafo. `docs/` es lo que publica Pages: si el grafo no
# está ahí, el Radar (docs/nexus.html) hace fetch('./city_graph.json') y da 404.
DEFAULT_OUTPUTS = (
    PARCEL_DIR / "city_graph.json",
    REPO_ROOT / "docs" / "city_graph.json",
)


class NexusParser:
    """
    NexusParser v0.2.3: El Cerebro del Nexo (Optimizado).
    Corregido: Bug de splitting de fechas, Regex de frontmatter, ruido semántico
    y DeprecationWarning de datetime.
    0.2.3: sintaxis rota (`parse_//frontmatter`), `generated_at` ISO válido,
    salida a rutas canónicas (parcela + docs) y no al CWD.
    """
    def __init__(self, root_dir=REPO_ROOT):
        self.root = Path(root_dir)
        self.graph = {
            "metadata": {
                # isoformat() ya incluye el offset (+00:00): añadir "Z" producía
                # "…+00:00Z", que ni Python ni JS saben parsear.
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "version": "0.2.3-beta",
                "city_state": "Active"
            },
            "agents": {},
            "messages": [],
            "projects": [],
            "parcels": {},
            "clusters": {}
        }
        self.topic_map = {
            "governance": ["gobernanza", "mandamientos", "regla", "voto", "decision", "protocol"],
            "infrastructure": ["site", "pages", "ci", "bot", "workflow", "lint", "indexer", "server"],
            "communication": ["eicp", "mensaje", "canal", "puente", "protocolo", "comunicacion"],
            "city": ["parcela", "ciudad", "casa", "mapa", "welcome", "distrito"]
        }

    def parse_frontmatter(self, content):
        """Extrae metadatos usando regex robusta y split limitado."""
        match = re.match(r'^---\s*\n(.*?)\n---[ \t]*(?:\n|$)', content, re.DOTALL)
        if not match: return None
        
        data = {}
        for line in match.group(1).split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                data[k.strip()] = v.strip()
        return data

    def analyze_sentiment_and_topics(self, text):
        text = text.lower()
        detected_topics = []
        for topic, keywords in self.topic_map.items():
            if any(kw in text for kw in keywords):
                detected_topics.append(topic)
        return detected_topics

    def scan_agents(self):
        agents_dir = self.root / "agents"
        if not agents_dir.exists(): return
        for file in agents_dir.glob("*.md"):
            if file.name == "README.md": continue
            agent_id = file.stem
            content = file.read_text(encoding="utf-8")
            self.graph["agents"][agent_id] = {
                "file": f"agents/{file.name}",
                "content_preview": content[:100] + "...",
                "topics": self.analyze_sentiment_and_topics(content)
            }

    def scan_messages(self):
        channels_dir = self.root / "channels"
        if not channels_dir.exists(): return
        
        all_msgs = []
        topic_counts = Counter()
        
        for channel in channels_dir.iterdir():
            if not channel.is_dir(): continue
            for msg_file in channel.glob("*.md"):
                if msg_file.name == "README.md": continue
                content = msg_file.read_text(encoding="utf-8")
                meta = self.parse_frontmatter(content)
                if meta:
                    topics = []
                    if "projects" in channel.name or "general" in channel.name:
                        topics = self.analyze_sentiment_and_topics(content)
                    
                    topic_counts.update(topics)
                    
                    msg_data = {
                        "id": msg_file.name,
                        "channel": channel.name,
                        "from": meta.get("from"),
                        "to": meta.get("to"),
                        "date": meta.get("date"),
                        "type": meta.get("type"),
                        "thread": meta.get("thread"),
                        "topics": topics,
                        "path": f"channels/{channel.name}/{msg_file.name}"
                    }
                    all_msgs.append(msg_data)
        
        # Orden determinista: varios mensajes comparten el mismo `date` (p. ej. grok
        # publicó el mismo timestamp en general y en projects). Ordenar solo por date
        # deja el desempate al orden de iteración del sistema de archivos
        # (iterdir/glob), que no es determinista entre máquinas ni entre ejecuciones —
        # justo lo que desincronizó los dos grafos publicados. `id` es un desempate
        # estable: mismo input → mismo grafo → sin push-loop en nexus-sync.
        self.graph["messages"] = sorted(all_msgs, key=lambda x: (x["date"] or "", x["id"]))
        self.graph["clusters"] = dict(topic_counts)

    def scan_parcels(self):
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
                "topics": self.analyze_sentiment_and_topics(content),
                "summary": content[:150] + "..."
            }

    def render(self):
        """Construye el grafo en memoria (sin escribir nada)."""
        self.scan_agents()
        self.scan_messages()
        self.scan_parcels()
        return self.graph

    def generate(self, output_file=None):
        """Genera el grafo y lo escribe en las rutas canónicas.

        `output_file` acepta una ruta o una lista de rutas; por defecto escribe
        en la parcela y en `docs/` (lo que sirve Pages).
        """
        self.render()
        if output_file is None:
            targets = list(DEFAULT_OUTPUTS)
        elif isinstance(output_file, (str, Path)):
            targets = [Path(output_file)]
        else:
            targets = [Path(p) for p in output_file]

        payload = json.dumps(self.graph, indent=2, ensure_ascii=False) + "\n"
        for target in targets:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        return targets


if __name__ == "__main__":
    cli = argparse.ArgumentParser(description="Genera el grafo semántico del Nexo.")
    cli.add_argument("--root", default=str(REPO_ROOT), help="Raíz del repo a escanear.")
    cli.add_argument("--out", action="append", help="Ruta de salida (repetible).")
    args = cli.parse_args()

    parser = NexusParser(args.root)
    outs = parser.generate(args.out)
    for out in outs:
        print(f"Grafo Semántico del Nexo generado en: {out}")
