from backend.app.services.source_criteria_service import SourceCriteriaService


def medication(name: str) -> dict[str, str]:
    return {"entered_name": name, "normalized_active_ingredient": name}


def result_by_id(results: list[dict], source_id: str) -> dict:
    return next(item for item in results if item["criterion_code"] == source_id)


def test_catalog_contains_exactly_the_297_source_rows() -> None:
    service = SourceCriteriaService()
    summary = service.summary()
    rows = service.criteria_coverage()

    assert summary["criterion_count"] == 297
    assert summary["stopp_count"] == 133
    assert summary["start_count"] == 57
    assert summary["beers_count"] == 107
    assert len(rows) == 297
    assert len({row["code"] for row in rows}) == 297
    assert rows[0]["code"] == "STOPP-001"
    assert rows[-1]["code"] == "Beers-107"


def test_every_row_has_an_executable_exposure_or_a_supported_special_kind() -> None:
    criteria = SourceCriteriaService()._load()["criteria"]
    supported_special = {
        "missing_indication",
        "excess_duration",
        "duplicate_class",
        "co_treatment_omission",
    }
    unreachable = [
        row["source_id"]
        for row in criteria
        if not row.get("medication_terms")
        and not row.get("group_terms")
        and not row.get("presence_field")
        and row["kind"] not in supported_special
    ]
    malformed_interactions = [
        row["source_id"]
        for row in criteria
        if row["kind"] == "interaction" and not row.get("interaction_config")
    ]
    assert unreachable == []
    assert malformed_interactions == []


def test_metformin_uses_egfr_for_stopp_071() -> None:
    _, low_results = SourceCriteriaService().evaluate(
        [medication("metformina")],
        age=75,
        sex="F",
        clinical_context={"egfr_ml_min_1_73m2": 25},
    )
    _, normal_results = SourceCriteriaService().evaluate(
        [medication("metformina")],
        age=75,
        sex="F",
        clinical_context={"egfr_ml_min_1_73m2": 45},
    )

    assert result_by_id(low_results, "STOPP-071")["status"] == "alert"
    assert result_by_id(normal_results, "STOPP-071")["status"] == "no_alert"


def test_stopp_121_uses_compact_fall_cie10_code() -> None:
    _, results = SourceCriteriaService().evaluate(
        [medication("morfina")],
        age=80,
        sex="F",
        clinical_context={},
        diagnoses="Caída no especificada W190",
    )
    criterion = result_by_id(results, "STOPP-121")
    assert criterion["status"] == "alert"
    assert criterion["context_used"]["falls_history"] is True
    assert any(item["field"] == "falls_history" for item in criterion["diagnosis_evidence"])


def test_beers_073_requires_one_medication_from_each_interaction_side() -> None:
    service = SourceCriteriaService()
    _, two_opioids = service.evaluate(
        [medication("morfina"), medication("tramadol")],
        age=72,
        sex="M",
        clinical_context={},
    )
    _, opioid_and_benzodiazepine = service.evaluate(
        [medication("morfina"), medication("clonazepam")],
        age=72,
        sex="M",
        clinical_context={},
    )

    assert result_by_id(two_opioids, "Beers-073")["status"] == "no_alert"
    assert result_by_id(opioid_and_benzodiazepine, "Beers-073")["status"] == "alert"


def test_stopp_003_excludes_prn_and_covers_non_nsaid_groups() -> None:
    medications = [medication("enalapril"), medication("captopril")]
    regular_context = {
        "medication_facts": [
            {"active_ingredient": "enalapril", "regular_use": True},
            {"active_ingredient": "captopril", "regular_use": True},
        ]
    }
    prn_context = {
        "medication_facts": [
            {"active_ingredient": "enalapril", "regular_use": True},
            {"active_ingredient": "captopril", "regular_use": False},
        ]
    }

    _, regular_results = SourceCriteriaService().evaluate(
        medications, age=70, sex="M", clinical_context=regular_context
    )
    _, prn_results = SourceCriteriaService().evaluate(
        medications, age=70, sex="M", clinical_context=prn_context
    )

    assert result_by_id(regular_results, "STOPP-003")["status"] == "alert"
    assert result_by_id(prn_results, "STOPP-003")["status"] == "no_alert"


def test_stopp_001_never_assumes_missing_indication_is_inappropriate() -> None:
    service = SourceCriteriaService()
    _, undocumented = service.evaluate(
        [medication("paracetamol")], age=70, sex="F", clinical_context={}
    )
    _, explicit = service.evaluate(
        [medication("paracetamol")],
        age=70,
        sex="F",
        clinical_context={
            "medication_facts": [
                {
                    "active_ingredient": "paracetamol",
                    "indication": "Sin indicación",
                    "indication_confirmed": False,
                }
            ]
        },
    )

    assert result_by_id(undocumented, "STOPP-001")["status"] == "not_evaluable"
    assert result_by_id(explicit, "STOPP-001")["status"] == "alert"


def test_start_001_requires_explicit_absence_of_the_indicated_treatment() -> None:
    service = SourceCriteriaService()
    _, missing_presence = service.evaluate(
        [],
        age=75,
        sex="F",
        clinical_context={"criterion_start_001_condition_met": True},
    )
    _, absent = service.evaluate(
        [],
        age=75,
        sex="F",
        clinical_context={
            "criterion_start_001_condition_met": True,
            "criterion_start_001_treatment_present": False,
        },
    )

    assert result_by_id(missing_presence, "START-001")["status"] == "not_evaluable"
    assert result_by_id(absent, "START-001")["status"] == "activated"


def test_selector_includes_explicit_source_medications() -> None:
    rows = SourceCriteriaService().source_medications_catalog()
    names = {row["medication"] for row in rows}
    assert "DIPIRIDAMOL" in names
    assert "MEBROBAMATO" not in names
    assert "MEPROBAMATO" in names
    assert "TIROIDES DISECADA" in names
    assert "SOMATROPINA" in names


def test_stopp_132_uses_the_daily_dose_calculated_for_paracetamol() -> None:
    _, results = SourceCriteriaService().evaluate(
        [medication("paracetamol")],
        age=77,
        sex="F",
        clinical_context={
            "criterion_stopp_132_condition_met": True,
            "medication_facts": [
                {"active_ingredient": "paracetamol", "daily_dose_mg": 3000}
            ]
        },
    )
    criterion = result_by_id(results, "STOPP-132")
    assert criterion["status"] == "alert"
    assert criterion["context_used"]["daily_dose_mg"] == 3000
