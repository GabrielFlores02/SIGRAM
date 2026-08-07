from pathlib import Path

import polars as pl

from backend.app.config import settings


def test_list_sample_patients(client):
    response = client.get("/api/pilot/v1/sample-patients")

    assert response.status_code == 200
    patients = response.json()
    assert len(patients) == 10
    assert all(item["patient_code"].startswith("PILOT-") for item in patients)
    assert all(item["index_date"] for item in patients)
    assert all(item["max_simultaneous_top_medications"] >= 1 for item in patients)


def test_evaluate_sample_patient_uses_overlap_episode(client):
    patients = client.get("/api/pilot/v1/sample-patients").json()
    patient = patients[0]

    response = client.post(
        f"/api/pilot/v1/sample-patients/{patient['patient_code']}/evaluate"
    )

    assert response.status_code == 200
    result = response.json()
    assert result["evaluation"]["successful"] is True
    assert result["evaluation"]["total_medications"] == patient[
        "max_simultaneous_top_medications"
    ]
    assert result["data_availability"]["medication_index_date"] == patient[
        "index_date"
    ]
    assert result["data_availability"]["clinical_observation_start_date"] == (
        "2025-01-01"
    )
    assert result["data_availability"]["clinical_observation_end_date"] == (
        "2025-12-31"
    )
    classifications = result["data_availability"][
        "medication_catalog_classification"
    ]
    assert len(classifications) == result["evaluation"]["total_medications"]
    assert all(item["essi_presentation"] for item in classifications)
    assert all(item["pharmacologic_group"] for item in classifications)
    assert all(
        item["status"] == "alert"
        for item in result["evaluation"]["clinical_findings"]
    )
    assert all(
        item["status"] == "not_evaluable"
        for item in result["evaluation"]["data_gaps"]
    )
    assert result["data_availability"]["labs_mapped_to_clinical_context"] is False
    assert {item["system"] for item in result["evaluation"]["analysis_results"]} == {
        "beers",
        "stopp_start",
        "ddinter",
    }


def test_evaluate_sample_patient_accepts_manual_context(client):
    patient_code = client.get("/api/pilot/v1/sample-patients").json()[0][
        "patient_code"
    ]

    response = client.post(
        f"/api/pilot/v1/sample-patients/{patient_code}/evaluate",
        json={
            "clinical_context": {
                "egfr_ml_min_1_73m2": 25,
                "falls_history": True,
                "indication_confirmed": True,
            }
        },
    )

    assert response.status_code == 200
    context = response.json()["case"]["clinical_context"]
    assert context["egfr_ml_min_1_73m2"] == 25
    assert context["falls_history"] is True
    assert context["medication_facts"]


def test_evaluate_unknown_sample_patient(client):
    response = client.post(
        "/api/pilot/v1/sample-patients/PILOT-NO-EXISTE/evaluate"
    )

    assert response.status_code == 404


def test_evaluate_sample_patient_maps_accepted_prior_labs(client):
    labs = pl.read_parquet(Path(settings.PILOT_SAMPLE_DIR) / "sample_labs_2025.parquet")
    patient_code = (
        labs.filter(
            (pl.col("analyte") == "HORMONA TSH")
            & (pl.col("result_value_raw") == "4.720")
        )
        .get_column("patient_code")
        .item(0)
    )
    response = client.post(
        f"/api/pilot/v1/sample-patients/{patient_code}/evaluate"
    )

    assert response.status_code == 200
    payload = response.json()
    context = payload["case"]["clinical_context"]
    availability = payload["data_availability"]
    assert context["tsh_miu_l"] == 4.72
    assert context["free_t4_normal"] is True
    assert availability["labs_mapped_to_clinical_context"] is True
    assert {item["field"] for item in availability["mapped_lab_fields"]} == {
        "tsh_miu_l",
        "free_t4_normal",
    }
    free_t4 = next(
        item
        for item in availability["mapped_lab_fields"]
        if item["field"] == "free_t4_normal"
    )
    assert free_t4["value"] is True


def test_evaluate_sample_patient_accepts_explicit_index_date(client):
    patient = client.get("/api/pilot/v1/sample-patients").json()[0]
    response = client.post(
        f"/api/pilot/v1/sample-patients/{patient['patient_code']}/evaluate",
        json={"index_date": patient["index_date"]},
    )

    assert response.status_code == 200
    assert response.json()["data_availability"]["medication_index_date"] == patient[
        "index_date"
    ]


def test_evaluate_sample_patient_rejects_index_date_outside_2025(client):
    patient_code = client.get("/api/pilot/v1/sample-patients").json()[0][
        "patient_code"
    ]
    response = client.post(
        f"/api/pilot/v1/sample-patients/{patient_code}/evaluate",
        json={"index_date": "2024-12-31"},
    )

    assert response.status_code == 422


def test_evaluate_sample_patient_applies_atenmed_cie10_context(client):
    patients = client.get("/api/pilot/v1/sample-patients").json()
    payload = None
    for patient in patients:
        response = client.post(
            f"/api/pilot/v1/sample-patients/{patient['patient_code']}/evaluate"
        )
        candidate = response.json()
        if any(
            item["satisfies_context_field"]
            for item in candidate["data_availability"]["mapped_diagnosis_fields"]
        ):
            payload = candidate
            break

    assert payload is not None
    availability = payload["data_availability"]
    assert availability["diagnosis_source"].endswith("from atenmed.parquet")
    assert availability["diagnosis_rows_considered"] > 0
    assert availability["distinct_diagnosis_codes"] > 0
    assert payload["case"]["clinical_context"]["diagnosis_codes"]
