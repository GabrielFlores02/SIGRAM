import pytest
from backend.app.models.models import ClinicalCase

# Helper to create a clinical case payload
def _create_case_payload(case_code, medications_list):
    meds = []
    for i, med_name in enumerate(medications_list):
        meds.append({
            "entered_name": f"{med_name} 10mg",
            "normalized_active_ingredient": med_name,
            "dose": "10mg",
            "dose_unit": "mg",
            "frequency": "diaria",
            "route": "oral"
        })
    return {
        "case_code": case_code,
        "age": 75,
        "sex": "M",
        "diagnoses": "Hipertensión de prueba",
        "is_simulated": True,
        "medications": meds
    }


def test_evaluate_nonexistent_case(client):
    """1. evaluar caso inexistente devuelve 404."""
    response = client.post("/api/cases/999999/evaluate")
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"].lower()


def test_evaluate_valid_case_no_alerts(client):
    """2. evaluar caso válido sin alertas (1 solo medicamento)."""
    # Crear caso con 1 medicamento
    payload = _create_case_payload("CASE-NO-ALERT", ["Enalapril"])
    res_create = client.post("/api/cases", json=payload)
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Evaluar
    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["successful"] is True
    assert data["total_medications"] == 1
    assert data["total_alerts"] == 0
    assert len(data["alerts"]) == 0
    assert data["processing_time_ms"] >= 0


def test_evaluate_polypharmacy_rule(client):
    """3. caso con cinco medicamentos genera REG-POLY-001."""
    payload = _create_case_payload("CASE-POLY", ["M1", "M2", "M3", "M4", "M5"])
    res_create = client.post("/api/cases", json=payload)
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Evaluar
    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["total_alerts"] == 1
    assert data["alerts"][0]["rule_code"] == "REG-POLY-001"
    assert data["alerts"][0]["severity"] == "advertencia"


def test_evaluate_duplicate_rule(client):
    """4. duplicidad genera REG-DUP-001."""
    payload = _create_case_payload("CASE-DUP", ["Aspirina", "aspirina"])
    res_create = client.post("/api/cases", json=payload)
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Evaluar
    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["total_alerts"] == 1
    assert data["alerts"][0]["rule_code"] == "REG-DUP-001"


def test_evaluate_demo_a_demo_b_interaction(client):
    """5. DEMO_A + DEMO_B genera REG-DEMO-INT-001."""
    payload = _create_case_payload("CASE-INT-AB", ["medicamento_demo_a", "medicamento_demo_b"])
    res_create = client.post("/api/cases", json=payload)
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Evaluar
    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["total_alerts"] == 1
    assert data["alerts"][0]["rule_code"] == "REG-DEMO-INT-001"
    assert data["alerts"][0]["severity"] == "moderada"
    systems = {item["system"]: item for item in data["analysis_results"]}
    assert systems["beers"]["status"] == "active_v1_screening_catalog"
    assert systems["stopp_start"]["status"] == "active_v1_screening_catalog"
    assert systems["ddinter"]["status"] == "active_local_legacy_catalog"


def test_evaluate_demo_c_demo_d_interaction(client):
    """6. DEMO_C + DEMO_D genera REG-DEMO-INT-002."""
    payload = _create_case_payload("CASE-INT-CD", ["medicamento_demo_c", "medicamento_demo_d"])
    res_create = client.post("/api/cases", json=payload)
    assert res_create.status_code == 201
    case_id = res_create.json()["id"]

    # Evaluar
    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["total_alerts"] == 1
    assert data["alerts"][0]["rule_code"] == "REG-DEMO-INT-002"
    assert data["alerts"][0]["severity"] == "alta"


def test_evaluate_real_ddinter_local_interaction(client):
    """El catálogo local real genera una alerta DDInter separada."""
    payload = _create_case_payload("CASE-DDINTER-REAL", ["Naltrexone", "Abacavir"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    ddinter_alerts = [
        item for item in data["alerts"] if item["analysis_system"] == "ddinter"
    ]
    assert len(ddinter_alerts) == 1
    assert ddinter_alerts[0]["is_demo"] is False
    systems = {item["system"]: item for item in data["analysis_results"]}
    assert systems["ddinter"]["alert_count"] == 1


def test_evaluate_alerts_sorted_by_severity(client):
    """7. múltiples alertas se guardan en orden de severidad (alta, moderada, advertencia)."""
    payload = _create_case_payload(
        "CASE-ALL-RULES", 
        ["medicamento_demo_a", "medicamento_demo_b", "medicamento_demo_c", "medicamento_demo_d", "medicamento_demo_a"]
    )
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    # Evaluar
    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.status_code == 200
    data = res_eval.json()
    assert data["total_alerts"] == 4
    
    severities = [alert["severity"] for alert in data["alerts"]]
    assert severities == ["alta", "moderada", "advertencia", "advertencia"]


def test_evaluate_processing_time_is_non_negative(client):
    """8. processing_time_ms es no negativo."""
    payload = _create_case_payload("CASE-TIME", ["Enalapril"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.json()["processing_time_ms"] >= 0.0


def test_evaluate_successful_flag(client):
    """9. successful=True en evaluación correcta."""
    payload = _create_case_payload("CASE-SUCCESS", ["Enalapril"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.json()["successful"] is True
    assert res_eval.json()["functional_error"] is False


def test_evaluate_total_medications_match(client):
    """10. total_medications coincide con el caso."""
    payload = _create_case_payload("CASE-MEDS-MATCH", ["M1", "M2", "M3"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    assert res_eval.json()["total_medications"] == 3


def test_evaluate_total_alerts_match(client):
    """11. total_alerts coincide con las alertas persistidas."""
    payload = _create_case_payload("CASE-ALERTS-MATCH", ["A", "B", "C", "D", "E"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    data = res_eval.json()
    assert data["total_alerts"] == len(data["alerts"])


def test_evaluate_trace_data_fields(client):
    """12. trace_data incluye execution_id, case_id y campos de RuleEngine."""
    payload = _create_case_payload("CASE-TRACE", ["A", "A"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    data = res_eval.json()
    trace = data["alerts"][0]["trace_data"]
    assert "execution_id" in trace
    assert trace["execution_id"] == data["id"]
    assert "case_id" in trace
    assert trace["case_id"] == case_id
    assert "evaluated_at" in trace
    assert "condition_evaluated" in trace
    assert "input_count" in trace
    assert "normalized_medications" in trace
    assert "implicated_medications" in trace


def test_evaluate_each_call_creates_different_execution(client):
    """13. cada nueva evaluación crea una ejecución diferente."""
    payload = _create_case_payload("CASE-MULTI-EVAL", ["Enalapril"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval1 = client.post(f"/api/cases/{case_id}/evaluate")
    res_eval2 = client.post(f"/api/cases/{case_id}/evaluate")

    assert res_eval1.json()["id"] != res_eval2.json()["id"]


def test_get_results_returns_latest_execution(client):
    """14. GET results devuelve la ejecución más reciente."""
    payload = _create_case_payload("CASE-LATEST", ["Enalapril"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval1 = client.post(f"/api/cases/{case_id}/evaluate")
    res_eval2 = client.post(f"/api/cases/{case_id}/evaluate")
    
    # GET results
    res_results = client.get(f"/api/cases/{case_id}/results")
    assert res_results.status_code == 200
    assert res_results.json()["id"] == res_eval2.json()["id"]


def test_get_execution_by_id(client):
    """15. GET execution devuelve la ejecución específica con sus alertas."""
    payload = _create_case_payload("CASE-BY-ID", ["medicamento_demo_a", "medicamento_demo_b"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    res_eval = client.post(f"/api/cases/{case_id}/evaluate")
    exec_id = res_eval.json()["id"]

    res_get = client.get(f"/api/executions/{exec_id}")
    assert res_get.status_code == 200
    assert res_get.json()["id"] == exec_id
    assert len(res_get.json()["alerts"]) == 1


def test_get_execution_nonexistent_returns_404(client):
    """16. ejecución inexistente devuelve 404."""
    response = client.get("/api/executions/999999")
    assert response.status_code == 404
    assert "no encontrada" in response.json()["detail"].lower()


def test_get_results_nonexistent_case_returns_404(client):
    """GET results de caso inexistente devuelve 404."""
    response = client.get("/api/cases/999999/results")
    assert response.status_code == 404


def test_get_results_no_evaluations_returns_404(client):
    """GET results de caso sin evaluaciones previas devuelve 404."""
    payload = _create_case_payload("CASE-NO-EVAL-YET", ["Enalapril"])
    res_create = client.post("/api/cases", json=payload)
    case_id = res_create.json()["id"]

    response = client.get(f"/api/cases/{case_id}/results")
    assert response.status_code == 404
    assert "no se encontraron evaluaciones previas" in response.json()["detail"].lower()


def test_evaluate_case_without_medications(client, db_session):
    """evaluar caso válido sin medicamentos devuelve 422 y no ejecuta el motor."""
    case_obj = ClinicalCase(
        case_code="CASE-NO-MEDS-DB",
        age=65,
        sex="M",
        diagnoses="Ninguno",
        is_simulated=True,
        status="active"
    )
    db_session.add(case_obj)
    db_session.commit()
    db_session.refresh(case_obj)

    response = client.post(f"/api/cases/{case_obj.id}/evaluate")
    assert response.status_code == 422
    assert "no contiene medicamentos" in response.json()["detail"].lower()
