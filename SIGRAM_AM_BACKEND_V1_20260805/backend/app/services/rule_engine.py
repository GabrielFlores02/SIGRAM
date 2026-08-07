from typing import List, Dict, Any
from backend.app.services.medication_normalizer import normalize_active_ingredient
from backend.app.services.demo_interaction_provider import DemoInteractionProvider
from backend.app.services.ddinter_csv_provider import DDInterCsvProvider

class RuleEngine:
    @staticmethod
    def evaluate(medications: List[str], interaction_providers=None) -> List[Dict[str, Any]]:
        """Evalúa una lista de principios activos de medicamentos y genera alertas demostrativas.

        - Rechaza listas nulas (lanza ValueError).
        - Acepta listas vacías y retorna una lista vacía de alertas.
        - Normaliza los valores de entrada.
        - Ejecuta las reglas REG-POLY-001 y REG-DUP-001.
        - Consulta DemoInteractionProvider para combinaciones de interacciones sintéticas.
        - Elimina alertas duplicadas.
        - Ordena por severidad: alta -> moderada -> advertencia.
        """
        if medications is None:
            raise ValueError("La lista de medicamentos no puede ser nula.")

        if not medications:
            return []

        # 1. Normalizar los valores
        normalized_meds = [normalize_active_ingredient(med) for med in medications]
        input_count = len(medications)
        alerts = []

        # 2. Regla REG-POLY-001: Polifarmacia
        if input_count >= 5:
            implicated = sorted(list(set(normalized_meds)))
            alerts.append({
                "rule_code": "REG-POLY-001",
                "alert_type": "polifarmacia",
                "severity": "advertencia",
                "problem_identified": "presencia de cinco o más medicamentos",
                "recommendation": "realizar revisión integral de la farmacoterapia",
                "justification": "el caso contiene cinco o más medicamentos registrados simultáneamente",
                "source": "definición operacional del protocolo SIGRAM-AM",
                "rule_version": "1.0",
                "is_demo": False,
                "analysis_system": "cohort_eligibility",
                "implicated_medications": implicated,
                "trace_data": {
                    "condition_evaluated": "input_count >= 5",
                    "input_count": input_count,
                    "normalized_medications": normalized_meds,
                    "implicated_medications": implicated,
                    "rule_code": "REG-POLY-001",
                    "rule_version": "1.0",
                    "analysis_system": "cohort_eligibility"
                }
            })

        # 3. Regla REG-DUP-001: Duplicidad exacta
        counts = {}
        for med in normalized_meds:
            counts[med] = counts.get(med, 0) + 1

        for med, count in counts.items():
            if count >= 2:
                implicated = [med]
                alerts.append({
                    "rule_code": "REG-DUP-001",
                    "alert_type": "posible duplicidad exacta",
                    "severity": "advertencia",
                    "problem_identified": "principio activo repetido",
                    "recommendation": "verificar duplicidad de registro o prescripción",
                    "justification": "se encontraron registros repetidos del mismo principio activo normalizado",
                    "source": "control lógico del prototipo",
                    "rule_version": "1.0",
                    "is_demo": True,
                    "analysis_system": "technical_demo",
                    "implicated_medications": implicated,
                    "trace_data": {
                        "condition_evaluated": f"count of {med} >= 2",
                        "input_count": input_count,
                        "normalized_medications": normalized_meds,
                        "implicated_medications": implicated,
                        "rule_code": "REG-DUP-001",
                        "rule_version": "1.0",
                        "analysis_system": "technical_demo"
                    }
                })

        # 4. Consultar DDInter local y conservar el proveedor sintético de la PoC.
        providers = interaction_providers
        if providers is None:
            providers = [DDInterCsvProvider(), DemoInteractionProvider()]
        interactions = []
        for provider in providers:
            interactions.extend(provider.find_interactions(normalized_meds))
        for interaction in interactions:
            implicated = interaction["implicated_medications"]
            alerts.append({
                "rule_code": interaction["rule_code"],
                "alert_type": interaction["alert_type"],
                "severity": interaction["severity"],
                "problem_identified": interaction["problem_identified"],
                "recommendation": interaction["recommendation"],
                "justification": interaction["justification"],
                "source": interaction["source"],
                "rule_version": interaction["rule_version"],
                "is_demo": interaction["is_demo"],
                "analysis_system": interaction.get(
                    "analysis_system", "technical_demo"
                ),
                "implicated_medications": implicated,
                "trace_data": {
                    "condition_evaluated": f"combination of {implicated[0]} and {implicated[1]} detected",
                    "input_count": input_count,
                    "normalized_medications": normalized_meds,
                    "implicated_medications": implicated,
                    "rule_code": interaction["rule_code"],
                    "rule_version": interaction["rule_version"]
                }
            })
            alerts[-1]["trace_data"]["analysis_system"] = alerts[-1][
                "analysis_system"
            ]
            for field in (
                "catalog_drugs",
                "catalog_ids",
                "catalog_level",
                "catalog_files",
            ):
                if field in interaction:
                    alerts[-1]["trace_data"][field] = interaction[field]

        # 5. Eliminar alertas duplicadas
        unique_alerts = []
        seen = set()
        for alert in alerts:
            # Clave única por código de regla y medicamentos implicados ordenados
            key = (alert["rule_code"], tuple(sorted(alert["implicated_medications"])))
            if key not in seen:
                seen.add(key)
                unique_alerts.append(alert)

        # 6. Ordenar por severidad: alta -> moderada -> advertencia
        severity_priority = {"alta": 1, "moderada": 2, "advertencia": 3}
        unique_alerts.sort(key=lambda x: severity_priority.get(x["severity"], 4))

        return unique_alerts
