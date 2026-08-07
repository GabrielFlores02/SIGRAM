from pathlib import Path
from datetime import datetime, timezone

from backend.app.config import settings
from backend.app.schemas.evaluations import EvaluationExecutionRead
from backend.app.services.clinical_catalog_service import ClinicalCatalogService


def _result_by_code(results, code):
    return next(item for item in results if item["criterion_code"] == code)


def test_catalog_v1_has_expected_scope():
    summary = ClinicalCatalogService().summary()
    assert summary["catalog_version"] == "2026-07-30-top-medications-v1"
    assert summary["medication_count"] == 54
    assert summary["criterion_count"] == 97
    assert summary["criteria_by_system"] == {"beers": 23, "stopp_start": 74}


def test_unconditional_beers_screen_generates_alert():
    alerts, results = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM"],
        age=75,
        sex="F",
        clinical_context={},
    )
    beers_alerts = [item for item in alerts if item["rule_code"] == "B01"]
    assert len(beers_alerts) == 1
    assert _result_by_code(results, "B01")["status"] == "alert"


def test_missing_falls_and_renal_function_are_reported():
    _, results = ClinicalCatalogService().evaluate(
        ["GABAPENTINA"],
        age=70,
        sex="M",
        clinical_context={},
    )
    b14 = _result_by_code(results, "B14")
    b19 = _result_by_code(results, "B19")
    assert b14["status"] == "not_evaluable"
    assert b14["missing_data"][0]["field"] == "falls_history"
    assert b19["status"] == "not_evaluable"
    assert b19["missing_data"][0]["field"] == "egfr_ml_min_1_73m2"


def test_metformin_low_egfr_generates_stopp_alert():
    alerts, results = ClinicalCatalogService().evaluate(
        ["METFORMINA"],
        age=80,
        sex="F",
        clinical_context={"egfr_ml_min_1_73m2": 25},
    )
    assert _result_by_code(results, "STOPP-E6")["status"] == "alert"
    assert any(item["rule_code"] == "STOPP-E6" for item in alerts)


def test_aine_without_ppi_generates_start_screen():
    alerts, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO"],
        age=72,
        sex="M",
        clinical_context={},
    )
    assert _result_by_code(results, "START-F3")["status"] == "alert"
    assert any(item["rule_code"] == "START-F3" for item in alerts)


def test_beers_60_to_64_is_marked_as_protocol_adaptation():
    _, results = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM"],
        age=62,
        sex="F",
        clinical_context={},
    )
    assert _result_by_code(results, "B01")["age_scope"] == "protocol_adaptation_60_64"


def test_duration_is_scoped_to_the_implicated_medication_and_b05_detects_combination():
    alerts, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO", "DEXAMETASONA", "ACIDO FOLICO"],
        age=72,
        sex="F",
        clinical_context={
            "medication_facts": [
                {"active_ingredient": "DICLOFENACO", "duration_days": 3},
                {"active_ingredient": "ACIDO FOLICO", "duration_days": 30},
            ]
        },
    )
    b05 = _result_by_code(results, "B05")
    assert b05["status"] == "alert"
    assert b05["context_used"]["medication_duration_days"] == 3
    assert {
        item.get("medication") for item in b05["triggering_evidence"]
    }.issuperset({"DICLOFENACO", "DEXAMETASONA"})
    assert "protector_not_found" in b05["exception_status"]
    assert any(item["rule_code"] == "B05" for item in alerts)


def test_complete_b05_exception_suppresses_alert_and_reports_protector():
    alerts, results = ClinicalCatalogService().evaluate(
        ["DICLOFENACO", "DEXAMETASONA", "OMEPRAZOL"],
        age=72,
        sex="F",
        clinical_context={
            "safer_alternatives_ineffective": True,
            "medication_facts": [
                {"active_ingredient": "DICLOFENACO", "duration_days": 3}
            ],
        },
    )
    b05 = _result_by_code(results, "B05")
    assert b05["status"] == "no_alert"
    assert b05["exception_status"] == "exception_applied"
    assert any(
        item.get("medication") == "OMEPRAZOL"
        for item in b05["protective_evidence"]
    )
    assert not any(item["rule_code"] == "B05" for item in alerts)


def test_b16_exception_for_opioid_transition_is_applied():
    _, alert_results = ClinicalCatalogService().evaluate(
        ["TRAMADOL", "GABAPENTINA"],
        age=75,
        sex="M",
        clinical_context={},
    )
    assert _result_by_code(alert_results, "B16")["status"] == "alert"

    _, excepted_results = ClinicalCatalogService().evaluate(
        ["TRAMADOL", "GABAPENTINA"],
        age=75,
        sex="M",
        clinical_context={"opioid_transition_or_dose_reduction": True},
    )
    b16 = _result_by_code(excepted_results, "B16")
    assert b16["status"] == "no_alert"
    assert b16["exception_status"] == "exception_applied"


def test_stopp_protective_coprescription_changes_result():
    base_context = {"peptic_ulcer_history": True}
    _, unprotected = ClinicalCatalogService().evaluate(
        ["DEXAMETASONA"], age=76, sex="F", clinical_context=base_context
    )
    assert _result_by_code(unprotected, "STOPP-F5")["status"] == "alert"

    _, protected = ClinicalCatalogService().evaluate(
        ["DEXAMETASONA", "OMEPRAZOL"],
        age=76,
        sex="F",
        clinical_context=base_context,
    )
    stopp_f5 = _result_by_code(protected, "STOPP-F5")
    assert stopp_f5["status"] == "no_alert"
    assert stopp_f5["exception_status"] == "protector_present"


def test_combination_precondition_prevents_irrelevant_missing_data():
    _, results = ClinicalCatalogService().evaluate(
        ["ACIDO ACETILSALICILICO"],
        age=78,
        sex="M",
        clinical_context={},
    )
    stopp_c4 = _result_by_code(results, "STOPP-C4")
    assert stopp_c4["status"] == "no_alert"
    assert stopp_c4["missing_data"] == []
    assert stopp_c4["exception_status"] == "not_applicable"


def test_catalog_and_source_endpoints(client):
    summary = client.get("/api/catalog/v1/summary")
    assert summary.status_code == 200
    assert summary.json()["medication_count"] == 54

    medications = client.get("/api/catalog/v1/medications")
    assert medications.status_code == 200
    assert len(medications.json()) == 54
    assert all(item["pharmacologic_group"] for item in medications.json())

    sources = client.get("/api/pilot/v1/sources")
    large_sources_present = all(
        Path(path).is_file()
        for path in (settings.PILOT_COHORT_FILE, settings.PILOT_LABS_FILE)
    )
    if large_sources_present:
        assert sources.status_code == 200
        assert sources.json()["status"] == "ready_for_local_prototype"
    else:
        assert sources.status_code == 503
        missing = set(sources.json()["detail"]["sources"])
        assert {"cohort", "laboratory_results"}.issubset(missing)


def test_api_separates_full_report_from_frontend_findings(client):
    payload = {
        "case_code": "CASE-V1-GABAPENTIN",
        "age": 62,
        "sex": "F",
        "diagnoses": "Dolor en evaluación",
        "is_simulated": True,
        "clinical_context": {},
        "medications": [
            {
                "entered_name": "Gabapentina 300 mg",
                "normalized_active_ingredient": "gabapentina",
                "dose": "300",
                "dose_unit": "mg",
                "frequency": "diaria",
                "route": "oral",
            }
        ],
    }
    created = client.post("/api/cases", json=payload)
    evaluated = client.post(f"/api/cases/{created.json()['id']}/evaluate")
    assert evaluated.status_code == 200
    data = evaluated.json()
    assert any(
        item["criterion_code"] == "B14"
        and item["status"] == "not_evaluable"
        for item in data["criteria_report"]
    )
    assert all(item["status"] == "alert" for item in data["clinical_findings"])
    assert any(item["criterion_code"] == "B14" for item in data["data_gaps"])
    systems = {item["system"]: item for item in data["analysis_results"]}
    assert systems["beers"]["not_evaluable_count"] >= 1


def test_classification_keeps_essi_presentation_and_group():
    class Medication:
        entered_name = "DICLOFENACO SÓDICO 25 MG / ML X 3 ML"
        normalized_active_ingredient = "DICLOFENACO"

    classification = ClinicalCatalogService().classify_medications([Medication()])
    assert classification
    assert classification[0]["essi_presentation"] == Medication.entered_name
    assert classification[0]["evaluation_name"] == "DICLOFENACO"
    assert classification[0]["matched_top_v1"] is True
    assert "ANTIINFLAMATORIO" in classification[0][
        "pharmacologic_group"
    ].upper()


def test_response_schema_preserves_legacy_rows_and_builds_frontend_views():
    _, technical_report = ClinicalCatalogService().evaluate(
        ["ALPRAZOLAM", "GABAPENTINA"],
        age=75,
        sex="F",
        clinical_context={},
    )
    assert any(item["status"] == "not_evaluable" for item in technical_report)
    now = datetime.now(timezone.utc)
    response = EvaluationExecutionRead.model_validate(
        {
            "id": 1,
            "case_id": 1,
            "started_at": now,
            "finished_at": now,
            "processing_time_ms": 1.0,
            "successful": True,
            "functional_error": False,
            "error_detail": None,
            "total_medications": 2,
            "total_alerts": 1,
            "created_at": now,
            "alerts": [],
            "criteria_report": technical_report,
        }
    )
    assert any(item.status == "not_evaluable" for item in response.criteria_report)
    assert response.clinical_findings
    assert all(item.status == "alert" for item in response.clinical_findings)
    assert response.data_gaps
    assert all(item.status == "not_evaluable" for item in response.data_gaps)
