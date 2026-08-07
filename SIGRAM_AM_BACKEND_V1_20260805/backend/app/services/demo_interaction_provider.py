from typing import List, Dict, Any
from backend.app.services.interaction_provider import InteractionProvider

class DemoInteractionProvider(InteractionProvider):
    def find_interactions(self, normalized_medications: List[str]) -> List[Dict[str, Any]]:
        """Busca combinaciones sintéticas demostrativas en la lista de medicamentos."""
        meds_set = {m.strip().upper() for m in normalized_medications if m}
        interactions = []

        # A. MEDICAMENTO_DEMO_A + MEDICAMENTO_DEMO_B
        if "MEDICAMENTO_DEMO_A" in meds_set and "MEDICAMENTO_DEMO_B" in meds_set:
            interactions.append({
                "rule_code": "REG-DEMO-INT-001",
                "alert_type": "interacción demostrativa",
                "severity": "moderada",
                "problem_identified": "combinación sintética detectada",
                "recommendation": "revisar la combinación",
                "justification": "combinación creada únicamente para validar el funcionamiento técnico",
                "source": "regla sintética de demostración",
                "rule_version": "1.0",
                "is_demo": True,
                "implicated_medications": ["MEDICAMENTO_DEMO_A", "MEDICAMENTO_DEMO_B"]
            })

        # B. MEDICAMENTO_DEMO_C + MEDICAMENTO_DEMO_D
        if "MEDICAMENTO_DEMO_C" in meds_set and "MEDICAMENTO_DEMO_D" in meds_set:
            interactions.append({
                "rule_code": "REG-DEMO-INT-002",
                "alert_type": "interacción demostrativa",
                "severity": "alta",
                "problem_identified": "combinación sintética de alta prioridad detectada",
                "recommendation": "solicitar evaluación profesional",
                "justification": "combinación creada únicamente para validar el funcionamiento técnico",
                "source": "regla sintética de demostración",
                "rule_version": "1.0",
                "is_demo": True,
                "implicated_medications": ["MEDICAMENTO_DEMO_C", "MEDICAMENTO_DEMO_D"]
            })

        return interactions
