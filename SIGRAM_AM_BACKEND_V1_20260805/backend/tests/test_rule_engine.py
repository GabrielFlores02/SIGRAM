import pytest
from backend.app.services.rule_engine import RuleEngine

def test_empty_list_returns_zero_alerts():
    """1. Lista vacía devuelve cero alertas."""
    alerts = RuleEngine.evaluate([])
    assert len(alerts) == 0


def test_null_list_raises_value_error():
    """Validación de rechazo de lista nula."""
    with pytest.raises(ValueError):
        RuleEngine.evaluate(None)


def test_four_medications_do_not_generate_polypharmacy():
    """2. Cuatro medicamentos no generan polifarmacia."""
    meds = ["M1", "M2", "M3", "M4"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 0


def test_five_medications_generate_polypharmacy():
    """3. Cinco medicamentos generan REG-POLY-001."""
    meds = ["M1", "M2", "M3", "M4", "M5"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    assert alerts[0]["rule_code"] == "REG-POLY-001"
    assert alerts[0]["severity"] == "advertencia"
    assert alerts[0]["alert_type"] == "polifarmacia"


def test_six_medications_generate_only_one_polypharmacy_alert():
    """4. Seis medicamentos generan una sola alerta de polifarmacia."""
    meds = ["M1", "M2", "M3", "M4", "M5", "M6"]
    alerts = RuleEngine.evaluate(meds)
    poly_alerts = [a for a in alerts if a["rule_code"] == "REG-POLY-001"]
    assert len(poly_alerts) == 1


def test_duplicate_active_ingredient_generates_dup_alert():
    """5. Principio activo repetido genera REG-DUP-001."""
    meds = ["Aspirina", "aspirina"]  # Normalizado a ASPIRINA
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    assert alerts[0]["rule_code"] == "REG-DUP-001"
    assert alerts[0]["alert_type"] == "posible duplicidad exacta"
    assert alerts[0]["implicated_medications"] == ["ASPIRINA"]


def test_three_repetitions_generate_only_one_dup_alert():
    """6. Tres repeticiones generan una sola alerta de duplicidad."""
    meds = ["Aspirina", "Aspirina", "aspirina"]
    alerts = RuleEngine.evaluate(meds)
    dup_alerts = [a for a in alerts if a["rule_code"] == "REG-DUP-001"]
    assert len(dup_alerts) == 1
    assert dup_alerts[0]["implicated_medications"] == ["ASPIRINA"]


def test_demo_a_and_demo_b_generates_moderate_alert():
    """7. DEMO_A + DEMO_B genera alerta moderada."""
    meds = ["medicamento_demo_a", "medicamento_demo_b"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    assert alerts[0]["rule_code"] == "REG-DEMO-INT-001"
    assert alerts[0]["severity"] == "moderada"


def test_demo_b_and_demo_a_no_duplicate_alert():
    """8. DEMO_B + DEMO_A no genera alerta duplicada."""
    meds = ["medicamento_demo_b", "medicamento_demo_a"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    assert alerts[0]["rule_code"] == "REG-DEMO-INT-001"


def test_demo_c_and_demo_d_generates_high_alert():
    """9. DEMO_C + DEMO_D genera alerta alta."""
    meds = ["medicamento_demo_c", "medicamento_demo_d"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    assert alerts[0]["rule_code"] == "REG-DEMO-INT-002"
    assert alerts[0]["severity"] == "alta"


def test_multiple_rules_are_sorted_by_severity():
    """10. Múltiples reglas se ordenan por severidad: alta -> moderada -> advertencia."""
    meds = ["medicamento_demo_a", "medicamento_demo_b", "medicamento_demo_c", "medicamento_demo_d", "medicamento_demo_a"]
    alerts = RuleEngine.evaluate(meds)
    
    assert len(alerts) == 4
    severities = [a["severity"] for a in alerts]
    assert severities == ["alta", "moderada", "advertencia", "advertencia"]
    
    assert alerts[0]["severity"] == "alta"
    assert alerts[1]["severity"] == "moderada"
    assert alerts[2]["severity"] == "advertencia"
    assert alerts[3]["severity"] == "advertencia"


def test_trace_data_contains_mandatory_fields():
    """11. trace_data contiene los campos obligatorios."""
    meds = ["medicamento_demo_a", "medicamento_demo_b"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    trace = alerts[0]["trace_data"]
    assert "condition_evaluated" in trace
    assert "input_count" in trace
    assert "normalized_medications" in trace
    assert "implicated_medications" in trace
    assert "rule_code" in trace
    assert "rule_version" in trace


def test_spaces_and_case_are_normalized():
    """12. Los espacios y mayúsculas se normalizan antes de evaluar."""
    meds = ["  medicamento_demo_a  ", "  medicamento_demo_b  "]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 1
    assert alerts[0]["rule_code"] == "REG-DEMO-INT-001"
    assert alerts[0]["implicated_medications"] == ["MEDICAMENTO_DEMO_A", "MEDICAMENTO_DEMO_B"]


def test_medications_without_interaction_do_not_generate_alerts():
    """13. Medicamentos sin interacción no generan alertas."""
    meds = ["Aspirina", "Metformina", "Atorvastatina"]
    alerts = RuleEngine.evaluate(meds)
    assert len(alerts) == 0
