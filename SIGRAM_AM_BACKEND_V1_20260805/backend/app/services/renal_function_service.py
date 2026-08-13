"""Cálculos renales trazables usados únicamente por el flujo piloto."""

from __future__ import annotations

import unicodedata
from typing import Any


COCKCROFT_GAULT_METHOD = "cockcroft_gault_actual_body_weight_v1"


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


def enrich_with_cockcroft_gault(
    context: dict[str, Any], *, age: int, sex: str
) -> dict[str, Any]:
    """Persist the calculated CrCl and its inputs without replacing a documented CrCl."""
    enriched = dict(context)
    if enriched.get("creatinine_clearance_ml_min") is not None:
        enriched.setdefault("creatinine_clearance_source", "documented")
        return enriched

    weight = enriched.get("weight_kg")
    creatinine = enriched.get("serum_creatinine_mg_dl")
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
