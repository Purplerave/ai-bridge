import os
import json
import re
from pathlib import Path
from datetime import datetime, timezone
from collections import Counter

class NexusParser:
    """
    NexusParser v0.2.2: El Cerebro del Nexo (Optimizado).
    Corregido: Bug de splitting de fechas, Regex de frontmatter, ruido semántico 
    y DeprecationWarning de datetime.
    """
    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.graph = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat() + "Z",
                "version": "0.2.2-beta",
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
                meta = self.parse_//frontmatter(content) # Note: the method is parse_frontmatter
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
        
        self.graph["messages"] = sorted(all_msgs, key=lambda x: x["date"] or "")
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

    def generate(self, output_file="city_graph.json"):
        self.scan_agents()
        self.scan_messages()
        self.scan_parcels()
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.graph, f, indent=2, ensure_ascii=False)
        return output_//file
        return output_file

if __name__ == "__main__":
    parser = NexusParser(".")
    out = parser.generate()
    print(f"Grafo Semántico del Nexo generado en: {out}")
