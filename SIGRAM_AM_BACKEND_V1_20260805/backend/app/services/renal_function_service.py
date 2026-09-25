"""Cálculos renales trazables usados únicamente por el flujo piloto."""

from __future__ import annotations

import unicodedata
from typing import Any


COCKCROFT_GAULT_METHOD = "cockcroft_gault_actual_body_weight_v1"
CKD_EPI_2021_CREATININE_METHOD = "ckd_epi_2021_creatinine_race_free"


def _canonical(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char)).upper()


def is_female(sex: str) -> bool:
    return _canonical(sex) in {"F", "FEMENINO", "MUJER"}


def cockcroft_gault_creatinine_clearance(
    *, age: int, sex: str, weight_kg: float, serum_creatinine_mg_dl: float
) -> float:
    """Estimate CrCl in mL/min using Cockcroft-Gault and actual body weight."""
    if age <= 0 or weight_kg <= 0 or serum_creatinine_mg_dl <= 0:
        raise ValueError("Edad, peso y creatinina sérica deben ser mayores que cero.")
    clearance = ((140 - age) * weight_kg) / (72 * serum_creatinine_mg_dl)
    if is_female(sex):
        clearance *= 0.85
    return round(clearance, 1)


def ckd_epi_2021_egfr(
    *, age: int, sex: str, serum_creatinine_mg_dl: float
) -> float:
    """Estimate eGFR in mL/min/1.73 m² using the 2021 race-free CKD-EPI equation."""
    if age < 18 or serum_creatinine_mg_dl <= 0:
        raise ValueError("Edad adulta y creatinina sérica mayor que cero son obligatorias.")
    female = is_female(sex)
    kappa = 0.7 if female else 0.9
    alpha = -0.241 if female else -0.302
    ratio = serum_creatinine_mg_dl / kappa
    estimate = (
        142
        * min(ratio, 1) ** alpha
        * max(ratio, 1) ** -1.2
        * 0.9938**age
        * (1.012 if female else 1)
    )
    return round(estimate, 1)


def enrich_with_cockcroft_gault(
    context: dict[str, Any], *, age: int, sex: str
) -> dict[str, Any]:
    """Persist CKD-EPI eGFR and Cockcroft-Gault CrCl without replacing documented values."""
    enriched = dict(context)
    creatinine = enriched.get("serum_creatinine_mg_dl")
    if enriched.get("egfr_ml_min_1_73m2") is not None:
        enriched.setdefault("egfr_source", "documented")
    elif creatinine is not None:
        estimate = ckd_epi_2021_egfr(
            age=age,
            sex=sex,
            serum_creatinine_mg_dl=float(creatinine),
        )
        inputs = {
            "age_years": age,
            "sex": sex,
            "serum_creatinine_mg_dl": float(creatinine),
            "serum_creatinine_date": enriched.get("serum_creatinine_date"),
        }
        enriched.update(
            {
                "egfr_ml_min_1_73m2": estimate,
                "egfr_source": "calculated",
                "egfr_method": CKD_EPI_2021_CREATININE_METHOD,
                "egfr_inputs": inputs,
            }
        )
        provenance = list(enriched.get("lab_provenance") or [])
        provenance.append(
            {
                "field": "egfr_ml_min_1_73m2",
                "value": estimate,
                "applied": True,
                "reason": "calculated_from_serum_creatinine",
                "source_analyte": "Creatinina sérica",
                "source_value_raw": str(creatinine),
                "source_unit": "mg/dL",
                "standardized_unit": "mL/min/1.73m2",
                "derived_method": CKD_EPI_2021_CREATININE_METHOD,
                "calculation_inputs": inputs,
                "quality_flags": [
                    "estimated_not_measured_gfr",
                    "requires_idms_traceable_serum_creatinine",
                ],
            }
        )
        enriched["lab_provenance"] = provenance

    if enriched.get("creatinine_clearance_ml_min") is not None:
        enriched.setdefault("creatinine_clearance_source", "documented")
        return enriched

    weight = enriched.get("weight_kg")
    if weight is None or creatinine is None:
        return enriched

    clearance = cockcroft_gault_creatinine_clearance(
        age=age,
        sex=sex,
        weight_kg=float(weight),
        serum_creatinine_mg_dl=float(creatinine),
    )
    enriched.update(
        {
            "creatinine_clearance_ml_min": clearance,
            "creatinine_clearance_source": "calculated",
            "creatinine_clearance_method": COCKCROFT_GAULT_METHOD,
            "creatinine_clearance_inputs": {
                "age_years": age,
                "sex": sex,
                "weight_kg": float(weight),
                "weight_basis": "actual_body_weight",
                "serum_creatinine_mg_dl": float(creatinine),
                "serum_creatinine_date": enriched.get("serum_creatinine_date"),
            },
        }
    )
    return enriched
