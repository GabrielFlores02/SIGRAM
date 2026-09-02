from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.app.config import settings
from backend.app.services.clinical_catalog_service import ClinicalCatalogService


router = APIRouter(prefix="/api", tags=["Clinical catalog V1"])


@router.get("/catalog/v1/summary")
def get_catalog_summary():
    """Resume el catálogo médico reducido utilizado por el prototipo V1."""
    return ClinicalCatalogService().summary()


@router.get("/catalog/v1/criteria")
def list_catalog_criteria(
    system: str | None = Query(default=None, pattern="^(beers|stopp_start)$"),
):
    """Lista criterios, datos requeridos y nivel de automatización V1."""
    return ClinicalCatalogService().criteria_coverage(system)


@router.get("/catalog/v1/medications")
def list_catalog_medications():
    """Lista grupos ampliados e identifica el subconjunto con reglas validadas."""
    return ClinicalCatalogService().medications_catalog()


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
