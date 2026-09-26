from pathlib import Path
import re
import unicodedata

from fastapi import APIRouter, HTTPException, Query

from backend.app.config import settings
from backend.app.services.clinical_catalog_service import ClinicalCatalogService
from backend.app.services.source_criteria_service import SourceCriteriaService


router = APIRouter(prefix="/api", tags=["Clinical catalog V1"])


def _medication_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", "", text.upper())


def _merged_medications() -> list[dict]:
    rows = ClinicalCatalogService().medications_catalog()
    rows.extend(SourceCriteriaService().source_medications_catalog())
    merged: dict[str, dict] = {}
    for item in rows:
        key = _medication_key(item["medication"])
        existing = merged.get(key)
        if not existing:
            merged[key] = dict(item)
            continue
        groups = {
            value.strip()
            for value in f"{existing.get('pharmacologic_group', '')} | {item.get('pharmacologic_group', '')}".split("|")
            if value.strip()
        }
        existing["pharmacologic_group"] = " | ".join(sorted(groups))
        for code_field in ("stopp_codes", "start_codes", "beers_codes"):
            existing[code_field] = sorted(set(existing.get(code_field, [])) | set(item.get(code_field, [])))
        existing["clinical_rules_validated"] = bool(
            existing.get("clinical_rules_validated") or item.get("clinical_rules_validated")
        )
        existing["reference_group_only"] = bool(
            existing.get("reference_group_only") and item.get("reference_group_only")
        )
    output = sorted(merged.values(), key=lambda item: _medication_key(item["medication"]))
    for order, item in enumerate(output, start=1):
        item["order"] = order
    return output


@router.get("/catalog/v1/summary")
def get_catalog_summary():
    """Resume el catálogo médico reducido utilizado por el prototipo V1."""
    legacy = ClinicalCatalogService().summary()
    direct = SourceCriteriaService().summary()
    return {
        **legacy,
        **direct,
        "pharmacologic_group_medication_count": len(_merged_medications()),
        "manual_or_context_dependent_count": 0,
        "status": "297_source_criteria_implemented",
    }


@router.get("/catalog/v1/criteria")
def list_catalog_criteria(
    system: str | None = Query(default=None, pattern="^(beers|stopp_start)$"),
):
    """Lista criterios, datos requeridos y nivel de automatización V1."""
    return SourceCriteriaService().criteria_coverage(system)


@router.get("/catalog/v1/medications")
def list_catalog_medications():
    """Lista grupos ampliados e identifica el subconjunto con reglas validadas."""
    return _merged_medications()


@router.get("/pilot/v1/sources")
def get_pilot_source_status():
    """Informa disponibilidad de cohorte, examenes, CIE-10 y catalogo."""
    cohort = Path(settings.PILOT_COHORT_FILE)
    labs = Path(settings.PILOT_LABS_FILE)
    diagnoses = Path(settings.PILOT_DIAGNOSES_FILE)
    catalog = Path(settings.CLINICAL_CATALOG_FILE)
    sources = {
        "cohort": {
            "path": str(cohort),
            "exists": cohort.is_file(),
            "expected_rows": 1_185_657,
            "expected_unique_patients": 1_185_657,
        },
        "laboratory_results": {
            "path": str(labs),
            "exists": labs.is_file(),
            "expected_rows": 278_872_980,
            "cohort_patients_with_any_lab": 952_949,
            "cohort_patients_without_labs": 232_708,
        },
        "attention_diagnoses": {
            "path": str(diagnoses),
            "exists": diagnoses.is_file(),
            "expected_rows": 10_801_766,
            "cie10_columns": ["cie10_1_norm", "cie10_2_norm", "cie10_3_norm"],
        },
        "clinical_catalog": {
            "path": str(catalog),
            "exists": catalog.is_file(),
        },
    }
    missing = [name for name, value in sources.items() if not value["exists"]]
    if missing:
        raise HTTPException(
            status_code=503,
            detail={"message": "Faltan fuentes locales del piloto.", "sources": missing},
        )
    return {
        "status": "ready_for_local_prototype",
        "sources": sources,
        "warning": "Los conteos son controles agregados; no implican evaluabilidad clínica completa.",
    }
