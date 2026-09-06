import json
from pathlib import Path
from collections import Counter

class NexusOracle:
    """
    NexusOracle: El intérprete de la Ciudad.
    Permite realizar consultas analíticas sobre el grafo del Nexo.
    """
    def __init__(self, graph_file="city_graph.json"):
        self.graph_file = Path(graph_file)
        self.data = self._load_graph()

    def _load_graph(self):
        if not self.graph_file.exists():
            return None
        with open(self.graph_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def get_most_active_agent(self):
        """Encuentra al agente con más conexiones en la ciudad."""
        if not self.data: return "No data"
        
        connections = Counter()
        for msg in self.data["messages"]:
            connections[msg["from"]] += 1
            if msg["to"] != "all":
                connections[msg["to"]] += 1
        
        if not connections: return "No active agents"
        top_agent, count = connections.most_common(1)[0]
        return f"{top_agent} con {count} interacciones."

    def get_dominant_topic(self):
        """Identifica el tema más discutido en la ciudad."""
        if not self.data: return "No data"
        clusters = self.data.get("clusters", {})
        if not clusters: return "No topics detected"
        
        top_topic, count = Counter(clusters).most_common(1)[0]
        return f"{top_topic} con {count} menciones."

    def get_agent_topics(self, agent_id):
        """Obtiene los temas predominantes de un agente específico."""
        if not self.data: return "No data"
        agent = self.data["agents"].get(agent_id)
        if not agent: return "Agent not found"
        
        topics = agent.get("topics", [])
        return ", ".join(topics) if topics else "Generalista"

    def query(self, command):
        """Interfaz de comandos simple para el Oráculo."""
        if not self.data: return "Error: Grafo no disponible."
        
        cmd = command.lower()
        if "activo" in cmd or "most active" in cmd:
            return f"El agente más activo es: {self.get_most_active_agent()}"
        elif "tema" in cmd or "dominant" in cmd or "topic" in cmd:
            return f"El tema predominante es: {self.get_dominant_topic()}"
        elif "quien es" in cmd or "who is" in cmd:
            agent_id = cmd.split("es")[-1].strip().replace(" ", "-")
            return f"El agente {agent_id} se especializa en: {self.get_agent_topics(agent_id)}"
        else:
            return "Comandos disponibles: 'activo', 'tema', 'quien es [nombre]'"

if __name__ == "__main__":
    # Ejecución de prueba
    oracle = NexusOracle("city_graph.json")
    print("--- ORÁCULO DEL NEXO v0.1 ---")
    print(f"Análisis rápido:\n- Actividad: {oracle.get_most_active_agent()}\n- Tendencia: {oracle.get_dominant_topic()}")
