"""Motor de tamizaje V1 para el catálogo clínico reducido del equipo médico."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from backend.app.config import settings


CATALOG_STATUS_ALERT = "alert"
CATALOG_STATUS_NO_ALERT = "no_alert"
CATALOG_STATUS_NOT_EVALUABLE = "not_evaluable"
CATALOG_STATUS_MANUAL_REVIEW = "manual_review"


FIELD_LABELS = {
    "indication_confirmed": "indicación clínica confirmada",
    "medication_duration_days": "duración estructurada del tratamiento",
    "daily_dose_mg": "dosis diaria total en mg",
    "gastroprotection": "presencia o indicación de gastroprotección",
    "heart_failure_status": "presencia y estado sintomático de insuficiencia cardiaca",
    "peptic_ulcer_history": "antecedente de úlcera o sangrado gastrointestinal",
    "egfr_ml_min_1_73m2": "TFGe/depuración renal",
    "primary_prevention": "indicación como prevención primaria o secundaria",
    "sodium_mmol_l": "sodio sérico",
    "delirium": "delirium o riesgo alto de delirium",
    "cognitive_impairment": "demencia o deterioro cognitivo",
    "falls_history": "antecedente de caídas o fracturas",
    "syncope_history": "antecedente de síncope",
    "orthostatic_hypotension": "hipotensión ortostática",
    "heart_rate_bpm": "frecuencia cardiaca",
    "av_block": "bloqueo auriculoventricular",
    "potassium_mmol_l": "potasio sérico",
    "corrected_calcium_mmol_l": "calcio corregido",
    "gout_history": "antecedente de gota",
    "potassium_monitoring": "vigilancia periódica de potasio",
    "qtc_ms": "intervalo QTc",
    "frailty_status": "estado de fragilidad",
    "life_expectancy_lt_3_years": "expectativa de vida menor de tres años",
    "cardiovascular_history": "enfermedad coronaria, cerebral o vascular periférica",
    "bleeding_risk": "riesgo clínico de hemorragia mayor",
    "atrial_fibrillation": "fibrilación auricular",
    "coronary_stent_or_stenosis": "stent coronario o estenosis coronaria documentada",
    "stable_vascular_disease": "enfermedad vascular estable",
    "constipation": "estreñimiento crónico",
    "copd": "EPOC moderada-grave",
    "respiratory_failure": "insuficiencia respiratoria o hipoxemia",
    "osteoarthritis": "artrosis",
    "prior_paracetamol_trial": "prueba terapéutica previa con paracetamol",
    "upper_gi_disease": "enfermedad gastrointestinal alta",
    "tsh_miu_l": "TSH",
    "free_t4_normal": "T4 libre y rango de referencia",
    "pain_severity": "intensidad del dolor",
    "first_line_treatment": "posición del medicamento en la línea terapéutica",
    "neuropathic_pain": "confirmación de dolor neuropático",
    "bmi": "índice de masa corporal",
    "chronic_liver_disease": "enfermedad hepática crónica",
    "systolic_bp_mm_hg": "presión arterial sistólica",
    "diastolic_bp_mm_hg": "presión arterial diastólica",
    "reduced_ejection_fraction": "fracción de eyección reducida",
    "proteinuria_mg_24h": "proteinuria o microalbuminuria cuantificada",
    "severe_gerd_or_stricture": "reflujo grave o estenosis péptica",
    "osteoporosis_or_fragility_fracture": "osteoporosis o fractura por fragilidad",
    "bph_urinary_symptoms": "síntomas urinarios por hiperplasia prostática",
    "opioid_regular_use": "uso regular de opioide",
    "opioid_transition_or_dose_reduction": (
        "transicion desde opioide o uso del gabapentinoide para reducir su dosis"
    ),
    "acute_severe_pain": "dolor agudo intenso",
    "ppi_maintenance_indication": "indicacion justificada de mantenimiento del IBP",
    "safer_alternatives_ineffective": "alternativas mas seguras ineficaces",
    "lithium_level_monitoring": "monitorizacion de concentraciones de litio",
}


REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "B04": ("medication_duration_days", "indication_confirmed"),
    "B05": ("medication_duration_days", "gastroprotection"),
    "B06": ("heart_failure_status",),
    "B07": ("peptic_ulcer_history", "gastroprotection"),
    "B08": ("egfr_ml_min_1_73m2",),
    "B09": ("primary_prevention",),
    "B11": ("sodium_mmol_l",),
    "B12": ("delirium",),
    "B13": ("cognitive_impairment",),
    "B14": ("falls_history",),
    "B19": ("egfr_ml_min_1_73m2",),
    "B20": ("egfr_ml_min_1_73m2",),
    "B21": ("egfr_ml_min_1_73m2",),
    "B23": ("syncope_history", "orthostatic_hypotension"),
    "STOPP-A1": ("indication_confirmed",),
    "STOPP-A2": ("medication_duration_days",),
    "STOPP-B4": ("heart_rate_bpm", "av_block"),
    "STOPP-B5": ("indication_confirmed",),
    "STOPP-B9": (
        "potassium_mmol_l",
        "sodium_mmol_l",
        "corrected_calcium_mmol_l",
        "gout_history",
    ),
    "STOPP-B12": ("potassium_mmol_l",),
    "STOPP-B13": ("potassium_monitoring",),
    "STOPP-B15": ("qtc_ms",),
    "STOPP-B16": ("frailty_status", "life_expectancy_lt_3_years"),
    "STOPP-B17": ("medication_duration_days", "cardiovascular_history"),
    "STOPP-B19": ("heart_failure_status",),
    "STOPP-C1": ("daily_dose_mg",),
    "STOPP-C2": ("bleeding_risk",),
    "STOPP-C4": ("atrial_fibrillation", "coronary_stent_or_stenosis"),
    "STOPP-C5": ("stable_vascular_disease",),
    "STOPP-C7": ("atrial_fibrillation",),
    "STOPP-C16": ("primary_prevention",),
    "STOPP-D8": ("medication_duration_days",),
    "STOPP-D9": ("cognitive_impairment", "indication_confirmed"),
    "STOPP-D10": ("medication_duration_days", "indication_confirmed"),
    "STOPP-D13": ("indication_confirmed",),
    "STOPP-D14": ("delirium", "cognitive_impairment"),
    "STOPP-E4": ("egfr_ml_min_1_73m2",),
    "STOPP-E6": ("egfr_ml_min_1_73m2",),
    "STOPP-E9": ("egfr_ml_min_1_73m2",),
    "STOPP-F2": ("medication_duration_days", "peptic_ulcer_history"),
    "STOPP-F3": ("constipation",),
    "STOPP-F5": ("peptic_ulcer_history", "gastroprotection"),
    "STOPP-G2": ("copd", "medication_duration_days"),
    "STOPP-G4": ("respiratory_failure",),
    "STOPP-H1": ("peptic_ulcer_history", "gastroprotection"),
    "STOPP-H2": ("systolic_bp_mm_hg", "diastolic_bp_mm_hg"),
    "STOPP-H3": (
        "medication_duration_days",
        "osteoarthritis",
        "prior_paracetamol_trial",
    ),
    "STOPP-H8": ("upper_gi_disease",),
    "STOPP-H9": ("medication_duration_days", "osteoarthritis"),
    "STOPP-I5": ("orthostatic_hypotension", "syncope_history"),
    "STOPP-J9": ("tsh_miu_l", "free_t4_normal"),
    "STOPP-K1": ("falls_history",),
    "STOPP-K3": ("falls_history", "orthostatic_hypotension"),
    "STOPP-K5": ("falls_history",),
    "STOPP-K7": ("falls_history",),
    "STOPP-K10": ("falls_history",),
    "STOPP-L1": ("pain_severity", "first_line_treatment"),
    "STOPP-L2": ("opioid_regular_use",),
    "STOPP-L5": ("neuropathic_pain",),
    "STOPP-L6": ("daily_dose_mg", "bmi", "chronic_liver_disease"),
    "START-B1": (
        "systolic_bp_mm_hg",
        "diastolic_bp_mm_hg",
        "frailty_status",
    ),
    "START-B2": (
        "cardiovascular_history",
        "frailty_status",
        "life_expectancy_lt_3_years",
    ),
    "START-B3": ("cardiovascular_history",),
    "START-B4": ("cardiovascular_history",),
    "START-B5": ("heart_failure_status", "reduced_ejection_fraction"),
    "START-B6": ("heart_failure_status", "reduced_ejection_fraction"),
    "START-B10": ("atrial_fibrillation", "heart_rate_bpm"),
    "START-C2": ("cardiovascular_history",),
    "START-E1": ("egfr_ml_min_1_73m2", "corrected_calcium_mmol_l"),
    "START-E4": ("proteinuria_mg_24h",),
    "START-F1": ("severe_gerd_or_stricture",),
    "START-F2": ("peptic_ulcer_history",),
    "START-F5": ("constipation",),
    "START-H2": ("medication_duration_days",),
    "START-H3": ("osteoporosis_or_fragility_fracture",),
    "START-H4": ("osteoporosis_or_fragility_fracture",),
    "START-I1": ("bph_urinary_symptoms",),
    "START-J1": ("proteinuria_mg_24h", "egfr_ml_min_1_73m2"),
    "START-K2": ("opioid_regular_use",),
}


AUTOMATED_CODES = {
    "B01",
    "B02",
    "B03",
    "B05",
    "B07",
    "B08",
    "B10",
    "B15",
    "B16",
    "B17",
    "B18",
    "B19",
    "B20",
    "B21",
    "B22",
    "STOPP-A3",
    "STOPP-B3",
    "STOPP-B12",
    "STOPP-B13",
    "STOPP-C4",
    "STOPP-C10",
    "STOPP-C14",
    "STOPP-D8",
    "STOPP-E4",
    "STOPP-E6",
    "STOPP-E9",
    "STOPP-F5",
    "STOPP-H1",
    "STOPP-H2",
    "STOPP-H3",
    "STOPP-H7",
    "STOPP-J1",
    "STOPP-J9",
    "STOPP-L2",
    "STOPP-L6",
    "STOPP-M1",
    "START-B1",
    "START-F3",
    "START-H9",
    "START-K2",
}


def _canonical(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != []


CNS_GROUP_TERMS = (
    "ANTICONVULSIVANTE",
    "BENZODIACEPINA",
    "OPIOIDE",
    "RELAJANTE MUSCULAR",
    "ANTIDEPRESIVO",
    "ANTIPSICOTICO",
)

# Umbral operativo del prototipo para traducir "uso cronico" del AINE.
# Debe ser ratificado por el catalogo definitivo del equipo medico.
CHRONIC_AINE_DAYS_V1 = 90


CRITERION_GUIDANCE: dict[str, dict[str, Any]] = {
    "B02": {
        "actions": [
            "Revisar la necesidad de orfenadrina y valorar una alternativa con menor carga anticolinergica y sedante."
        ]
    },
    "B03": {
        "actions": [
            "Incluir la orfenadrina en el recuento de carga anticolinergica y minimizar otros anticolinergicos."
        ]
    },
    "B04": {
        "exception_fields": ["ppi_maintenance_indication"],
        "actions": [
            "Confirmar duracion total y si existe una indicacion justificada de mantenimiento del IBP."
        ],
    },
    "B05": {
        "interacting_group_terms": [
            "CORTICOIDE SISTEMICO",
            "ANTICOAGULANTE",
            "ANTIAGREGANTE",
        ],
        "protective_group_terms": ["BOMBA DE PROTONES"],
        "protector_effect": "mitigates_only",
        "requires_protector_with_exception": True,
        "exception_fields": ["safer_alternatives_ineffective"],
        "actions": [
            "Confirmar la duracion real del AINE y si fallaron alternativas mas seguras.",
            "Si el AINE debe continuar, verificar gastroproteccion activa y revisar corticoides, anticoagulantes o antiagregantes concomitantes.",
        ],
    },
    "B06": {
        "actions": [
            "Confirmar insuficiencia cardiaca y estado sintomatico; si es sintomatica, revisar la retirada del AINE."
        ]
    },
    "B07": {
        "protective_group_terms": ["BOMBA DE PROTONES"],
        "protector_effect": "mitigates_only",
        "requires_protector_with_exception": True,
        "exception_fields": ["safer_alternatives_ineffective"],
        "actions": [
            "Confirmar antecedente de ulcera, alternativas mas seguras y gastroproteccion antes de mantener AAS/AINE."
        ],
    },
    "B08": {
        "actions": ["Obtener TFGe/depuracion renal; evitar el AINE si es menor de 30 mL/min."]
    },
    "B12": {
        "actions": [
            "Confirmar delirium o alto riesgo y reducir anticolinergicos, benzodiacepinas u opioides cuando corresponda."
        ]
    },
    "B13": {
        "actions": [
            "Confirmar demencia o deterioro cognitivo y minimizar medicamentos anticolinergicos o benzodiacepinas."
        ]
    },
    "B14": {
        "exception_fields": ["acute_severe_pain"],
        "actions": [
            "Confirmar caidas/fracturas y revisar alternativas mas seguras; en opioides, documentar si existe dolor agudo intenso."
        ],
    },
    "B16": {
        "exception_fields": ["opioid_transition_or_dose_reduction"],
        "actions": [
            "Evitar opioide con gabapentinoide salvo transicion o reduccion documentada de la dosis del opioide; aun con excepcion, vigilar sedacion."
        ],
    },
    "B15": {
        "actions": [
            "Evitar la combinacion de opioide y benzodiacepina; si no puede suspenderse de inmediato, revisar dosis, duracion y vigilancia de sedacion/depresion respiratoria."
        ],
    },
    "B17": {
        "actions": [
            "Reducir a menos de tres las clases activas sobre el sistema nervioso central cuando sea clinicamente posible."
        ]
    },
    "B18": {
        "actions": ["Minimizar el numero de medicamentos con carga anticolinergica."]
    },
    "B22": {
        "exception_fields": ["lithium_level_monitoring"],
        "actions": [
            "Evitar litio con IECA/ARA-II/ARNI o, si se mantiene, monitorizar concentraciones de litio."
        ],
    },
    "STOPP-B13": {
        "exception_fields": ["potassium_monitoring"],
        "actions": ["Asegurar vigilancia periodica del potasio si la combinacion se mantiene."],
    },
    "STOPP-C4": {
        "exception_fields": ["coronary_stent_or_stenosis"],
        "actions": [
            "Confirmar stent coronario o estenosis coronaria mayor de 50% antes de mantener antiagregante con anticoagulante."
        ],
    },
    "STOPP-F5": {
        "protective_group_terms": ["BOMBA DE PROTONES"],
        "protector_effect": "satisfies_exception",
        "actions": ["Coprescribir un IBP o revisar la necesidad del corticoide."],
    },
    "STOPP-H1": {
        "protective_group_terms": ["BOMBA DE PROTONES", "ANTAGONISTA H2"],
        "protector_effect": "satisfies_exception",
        "actions": ["Agregar gastroproteccion apropiada o revisar la necesidad del AINE."],
    },
    "STOPP-H3": {
        "exception_fields": ["prior_paracetamol_trial"],
        "actions": ["Confirmar una prueba previa adecuada con paracetamol antes del AINE prolongado."],
    },
    "STOPP-H7": {
        "actions": [
            "Evitar el uso concomitante de AINE y corticoide sistemico; revisar si uno puede retirarse y evaluar el riesgo gastrointestinal."
        ],
    },
    "STOPP-L2": {
        "protective_group_terms": ["LAXANTE"],
        "protector_effect": "satisfies_exception",
        "actions": ["Agregar un laxante concomitante o revisar el uso regular del opioide."],
    },
    "START-F2": {
        "protective_group_terms": ["BOMBA DE PROTONES"],
        "protector_effect": "resolves_omission",
        "actions": ["Considerar un IBP si se inicia AAS y existe antecedente ulceroso o esofagitis."],
    },
    "START-F3": {
        "protective_group_terms": ["BOMBA DE PROTONES"],
        "protector_effect": "resolves_omission",
        "actions": ["Considerar un IBP durante el tratamiento con AINE."],
    },
    "START-H9": {
        "protective_name_terms": ["ACIDO FOLICO"],
        "protector_effect": "resolves_omission",
        "actions": ["Considerar acido folico durante el tratamiento con metotrexato."],
    },
    "START-K2": {
        "protective_group_terms": ["LAXANTE"],
        "protector_effect": "resolves_omission",
        "actions": ["Considerar un laxante en el uso regular de opioides."],
    },
}


class ClinicalCatalogService:
    _catalog_cache: dict[str, Any] | None = None
    _catalog_signature: tuple[str, int, int] | None = None

    def __init__(self, catalog_path: str | Path | None = None):
        self.catalog_path = Path(catalog_path or settings.CLINICAL_CATALOG_FILE)

    def _load_catalog(self) -> dict[str, Any]:
        stat = self.catalog_path.stat()
        signature = (str(self.catalog_path.resolve()), stat.st_mtime_ns, stat.st_size)
        if (
            ClinicalCatalogService._catalog_cache is None
            or ClinicalCatalogService._catalog_signature != signature
        ):
            ClinicalCatalogService._catalog_cache = json.loads(
                self.catalog_path.read_text(encoding="utf-8")
            )
            ClinicalCatalogService._catalog_signature = signature
        return ClinicalCatalogService._catalog_cache

    def summary(self) -> dict[str, Any]:
        catalog = self._load_catalog()
        criteria = catalog["criteria"]
        by_system = Counter(item["system"] for item in criteria)
        automated = sum(item["code"] in AUTOMATED_CODES for item in criteria)
        return {
            "catalog_version": catalog["catalog_version"],
            "source_file": catalog["source_file"],
            "source_sha256": catalog["source_sha256"],
            "medication_count": catalog["medication_count"],
            "criterion_count": catalog["criterion_count"],
            "criteria_by_system": dict(by_system),
            "automated_criterion_count": automated,
            "manual_or_context_dependent_count": len(criteria) - automated,
            "population": catalog["population"],
            "status": "prototype_v1_screening_only",
        }

    def criteria_coverage(self, system: str | None = None) -> list[dict[str, Any]]:
        catalog = self._load_catalog()
        output = []
        for criterion in catalog["criteria"]:
            if system and criterion["system"] != system:
                continue
            required = list(REQUIREMENTS.get(criterion["code"], ()))
            output.append(
                {
                    **criterion,
                    "automation_status": (
                        "automated_v1"
                        if criterion["code"] in AUTOMATED_CODES
                        else "manual_or_context_dependent"
                    ),
                    "required_data": [
                        {
                            "field": field,
                            "label": FIELD_LABELS.get(field, field),
                        }
                        for field in required
                    ],
                }
            )
        return output

    def medications_catalog(self) -> list[dict[str, Any]]:
        """Expone la presentacion fuente, agrupacion y criterios del top V1."""
        return [dict(item) for item in self._load_catalog()["medications"]]

    def classify_medications(self, medications: list[Any]) -> list[dict[str, Any]]:
        """Clasifica cada presentacion recibida contra el catalogo medico V1."""
        catalog_rows = self._load_catalog()["medications"]
        output: list[dict[str, Any]] = []
        for medication in medications:
            evaluation_name = self._medication_name(medication)
            essi_presentation = self._entered_medication_name(medication)
            exact_presentation_matches = [
                item
                for item in catalog_rows
                if _canonical(essi_presentation) == _canonical(item["medication"])
            ]
            matches = exact_presentation_matches or [
                item
                for item in catalog_rows
                if self._matches(evaluation_name, item["medication"])
            ]
            if not matches:
                output.append(
                    {
                        "essi_presentation": essi_presentation,
                        "evaluation_name": evaluation_name,
                        "matched_top_v1": False,
                        "catalog_medication": None,
                        "pharmacologic_group": None,
                        "beers_codes": [],
                        "stopp_codes": [],
                        "start_codes": [],
                    }
                )
                continue
            for item in matches:
                output.append(
                    {
                        "essi_presentation": essi_presentation,
                        "evaluation_name": evaluation_name,
                        "matched_top_v1": True,
                        "catalog_medication": item["medication"],
                        "pharmacologic_group": item["pharmacologic_group"],
                        "beers_codes": list(item["beers_codes"]),
                        "stopp_codes": list(item["stopp_codes"]),
                        "start_codes": list(item["start_codes"]),
                    }
                )
        return output

    @staticmethod
    def _medication_name(medication: Any) -> str:
        if isinstance(medication, str):
            return medication
        return str(
            getattr(medication, "normalized_active_ingredient", None)
            or getattr(medication, "entered_name", None)
            or ""
        )

    @staticmethod
    def _entered_medication_name(medication: Any) -> str:
        if isinstance(medication, str):
            return medication
        return str(
            getattr(medication, "entered_name", None)
            or getattr(medication, "normalized_active_ingredient", None)
            or ""
        )

    @staticmethod
    def _matches(input_name: str, catalog_name: str) -> bool:
        entered = _canonical(input_name)
        catalog = _canonical(catalog_name)
        if not entered or not catalog:
            return False
        if entered == catalog:
            return True
        if len(entered) >= 5 and entered in catalog:
            return True
        root = re.split(r"\s+\d", catalog, maxsplit=1)[0]
        return len(root) >= 5 and (entered == root or root in entered)

    @staticmethod
    def _context_value(
        field: str,
        context: dict[str, Any],
        present_groups: list[str],
        implicated_medications: list[str] | None = None,
    ) -> Any:
        if field == "gastroprotection":
            explicit = context.get(field)
            if explicit is not None:
                return explicit
            return any("BOMBA DE PROTONES" in group for group in present_groups)
        if field == "medication_duration_days":
            facts = context.get("medication_facts") or []
            values = [
                item.get("duration_days")
                for item in facts
                if _present(item.get("duration_days"))
                and (
                    not implicated_medications
                    or any(
                        ClinicalCatalogService._matches(
                            str(item.get("active_ingredient") or ""), medication
                        )
                        for medication in implicated_medications
                    )
                )
            ]
            return max(values) if values else None
        if field == "daily_dose_mg":
            facts = context.get("medication_facts") or []
            values = [
                item.get("daily_dose_mg")
                for item in facts
                if _present(item.get("daily_dose_mg"))
                and (
                    not implicated_medications
                    or any(
                        ClinicalCatalogService._matches(
                            str(item.get("active_ingredient") or ""), medication
                        )
                        for medication in implicated_medications
                    )
                )
            ]
            return max(values) if values else None
        return context.get(field)

    @staticmethod
    def _profiles(
        present_names: list[str], present_groups: list[str]
    ) -> list[dict[str, str]]:
        return [
            {"medication": name, "pharmacologic_group": group}
            for name, group in zip(present_names, present_groups, strict=False)
        ]

    @staticmethod
    def _matching_profiles(
        profiles: list[dict[str, str]],
        *,
        group_terms: tuple[str, ...] | list[str] = (),
        name_terms: tuple[str, ...] | list[str] = (),
    ) -> list[dict[str, str]]:
        canonical_groups = [_canonical(item) for item in group_terms]
        canonical_names = [_canonical(item) for item in name_terms]
        return [
            profile
            for profile in profiles
            if any(
                term in _canonical(profile["pharmacologic_group"])
                for term in canonical_groups
            )
            or any(
                term in _canonical(profile["medication"])
                for term in canonical_names
            )
        ]

    @classmethod
    def _medication_precondition(
        cls,
        code: str,
        present_names: list[str],
        present_groups: list[str],
    ) -> tuple[bool | None, str | None]:
        profiles = cls._profiles(present_names, present_groups)

        def count_groups(*terms: str) -> int:
            return len(cls._matching_profiles(profiles, group_terms=terms))

        def count_names(*terms: str) -> int:
            return len(cls._matching_profiles(profiles, name_terms=terms))

        raas = count_groups("ARA II", "IECA", "ARNI")
        gates: dict[str, tuple[bool, str]] = {
            "B15": (
                count_groups("OPIOIDE") >= 1 and count_groups("BENZODIACEPINA") >= 1,
                "No se encontro simultaneamente un opioide y una benzodiacepina.",
            ),
            "B16": (
                count_groups("OPIOIDE") >= 1
                and count_names("GABAPENTINA", "PREGABALINA") >= 1,
                "No se encontro simultaneamente un opioide y un gabapentinoide.",
            ),
            "B17": (
                count_groups(*CNS_GROUP_TERMS) >= 3,
                "Se encontraron menos de tres medicamentos/clases activas sobre el SNC.",
            ),
            "B18": (
                count_groups("RELAJANTE MUSCULAR", "ANTICOLINERGICO") >= 2,
                "Se encontraron menos de dos medicamentos anticolinergicos en el catalogo V1.",
            ),
            "B21": (
                raas >= 2,
                "Se encontraron menos de dos inhibidores del sistema renina-angiotensina.",
            ),
            "B22": (
                count_names("LITIO") >= 1 and raas >= 1,
                "No se encontro la combinacion de litio con IECA/ARA-II/ARNI.",
            ),
            "STOPP-B3": (
                count_groups("BETABLOQUEADOR") >= 1
                and count_names("VERAPAMILO", "DILTIAZEM") >= 1,
                "No se encontro betabloqueador combinado con verapamilo o diltiazem.",
            ),
            "STOPP-B13": (
                count_groups("ANTAGONISTA DE ALDOSTERONA") >= 1 and raas >= 1,
                "No se encontro antagonista de aldosterona combinado con IECA/ARA-II u otro ahorrador de potasio.",
            ),
            "STOPP-C4": (
                count_groups("ANTIAGREGANTE") >= 1
                and count_groups("ANTICOAGULANTE") >= 1,
                "No se encontro antiagregante combinado con anticoagulante.",
            ),
            "STOPP-C5": (
                count_groups("ANTIAGREGANTE") >= 1
                and count_groups("ANTICOAGULANTE") >= 1,
                "No se encontro antiagregante combinado con anticoagulante.",
            ),
            "STOPP-C10": (
                count_groups("ANTIINFLAMATORIO NO ESTEROIDEO") >= 1
                and count_groups("ANTICOAGULANTE") >= 1,
                "No se encontro AINE combinado con anticoagulante.",
            ),
            "STOPP-C14": (
                count_names("AZITROMICINA") >= 1
                and count_names("APIXABAN", "DABIGATRAN", "EDOXABAN", "RIVAROXABAN")
                >= 1,
                "No se encontro azitromicina combinada con un anticoagulante oral directo implicado.",
            ),
            "STOPP-H7": (
                count_groups("ANTIINFLAMATORIO NO ESTEROIDEO") >= 1
                and count_groups("CORTICOIDE SISTEMICO") >= 1,
                "No se encontro AINE combinado con corticoide sistemico.",
            ),
            "STOPP-M1": (
                count_groups("RELAJANTE MUSCULAR", "ANTICOLINERGICO") >= 2,
                "Se encontraron menos de dos medicamentos anticolinergicos en el catalogo V1.",
            ),
            "START-H9": (
                count_names("METOTREXATO") >= 1,
                "No se encontro metotrexato; no aplica la omision de acido folico.",
            ),
        }
        return gates.get(code, (None, None))

    @classmethod
    def _logic_details(
        cls,
        code: str,
        *,
        status: str,
        reason: str,
        context: dict[str, Any],
        present_names: list[str],
        present_groups: list[str],
        implicated: list[str],
        missing_fields: list[str],
        precondition_reason: str | None,
    ) -> dict[str, Any]:
        profiles = cls._profiles(present_names, present_groups)
        guidance = CRITERION_GUIDANCE.get(code, {})
        triggering: list[dict[str, Any]] = [
            {
                "type": "medication",
                "role": "catalog_match",
                "medication": medication,
            }
            for medication in implicated
        ]

        evidence_terms: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
            "B15": (("OPIOIDE", "BENZODIACEPINA"), ()),
            "B16": (("OPIOIDE",), ("GABAPENTINA", "PREGABALINA")),
            "B17": (CNS_GROUP_TERMS, ()),
            "B18": (("RELAJANTE MUSCULAR", "ANTICOLINERGICO"), ()),
            "B21": (("ARA II", "IECA", "ARNI"), ()),
            "B22": (("ARA II", "IECA", "ARNI"), ("LITIO",)),
            "STOPP-B3": (("BETABLOQUEADOR",), ("VERAPAMILO", "DILTIAZEM")),
            "STOPP-B13": (("ANTAGONISTA DE ALDOSTERONA", "ARA II", "IECA"), ()),
            "STOPP-C4": (("ANTIAGREGANTE", "ANTICOAGULANTE"), ()),
            "STOPP-C5": (("ANTIAGREGANTE", "ANTICOAGULANTE"), ()),
            "STOPP-C10": (("ANTIINFLAMATORIO NO ESTEROIDEO", "ANTICOAGULANTE"), ()),
            "STOPP-C14": ((), ("AZITROMICINA", "APIXABAN", "DABIGATRAN", "EDOXABAN", "RIVAROXABAN")),
            "STOPP-H7": (("ANTIINFLAMATORIO NO ESTEROIDEO", "CORTICOIDE SISTEMICO"), ()),
            "STOPP-M1": (("RELAJANTE MUSCULAR", "ANTICOLINERGICO"), ()),
        }
        group_terms, name_terms = evidence_terms.get(code, ((), ()))
        related_profiles = cls._matching_profiles(
            profiles, group_terms=group_terms, name_terms=name_terms
        )
        related_profiles += cls._matching_profiles(
            profiles,
            group_terms=guidance.get("interacting_group_terms", []),
        )
        seen_triggering = {
            (item.get("medication"), item.get("role")) for item in triggering
        }
        for profile in related_profiles:
            key = (profile["medication"], "combination_or_risk_factor")
            if key in seen_triggering:
                continue
            seen_triggering.add(key)
            triggering.append(
                {
                    "type": "medication",
                    "role": "combination_or_risk_factor",
                    **profile,
                }
            )

        protective_profiles = cls._matching_profiles(
            profiles,
            group_terms=guidance.get("protective_group_terms", []),
            name_terms=guidance.get("protective_name_terms", []),
        )
        protective: list[dict[str, Any]] = [
            {
                "type": "medication",
                "role": "protector_or_required_coprescription",
                **profile,
            }
            for profile in protective_profiles
        ]

        exception_fields = list(guidance.get("exception_fields", []))
        if code == "B14" and not cls._matching_profiles(
            profiles, group_terms=("OPIOIDE",)
        ):
            exception_fields = []
        exception_values = {field: context.get(field) for field in exception_fields}
        for field, value in exception_values.items():
            if value is True:
                protective.append(
                    {
                        "type": "context",
                        "role": "documented_exception",
                        "field": field,
                        "value": value,
                    }
                )
            elif value is False:
                triggering.append(
                    {
                        "type": "context",
                        "role": "exception_not_met",
                        "field": field,
                        "value": value,
                    }
                )

        if status == CATALOG_STATUS_ALERT:
            for field in REQUIREMENTS.get(code, ()):
                value = cls._context_value(
                    field, context, present_groups, implicated
                )
                if not _present(value):
                    continue
                triggering.append(
                    {
                        "type": "context",
                        "role": "clinical_context_evaluated",
                        "field": field,
                        "label": FIELD_LABELS.get(field, field),
                        "value": value,
                    }
                )

        if context.get("gastroprotection") is True and not protective_profiles:
            protective.append(
                {
                    "type": "context",
                    "role": "documented_gastroprotection",
                    "field": "gastroprotection",
                    "value": True,
                }
            )

        exception_documented = any(
            value is True for value in exception_values.values()
        )
        protector_documented = bool(protective_profiles) or bool(
            context.get("gastroprotection")
        )
        requires_both = bool(guidance.get("requires_protector_with_exception"))

        if precondition_reason:
            exception_status = "not_applicable"
            exception_reason = precondition_reason
        elif requires_both and exception_documented and protector_documented:
            exception_status = "exception_applied"
            exception_reason = (
                "Se documentaron alternativas mas seguras ineficaces y gastroproteccion."
            )
        elif requires_both and (exception_documented or protector_documented):
            exception_status = "partial_exception_requires_confirmation"
            exception_reason = (
                "La excepcion esta incompleta: deben confirmarse tanto el fallo de "
                "alternativas mas seguras como la gastroproteccion."
            )
        elif exception_documented:
            exception_status = "exception_applied"
            exception_reason = "Se encontro una excepcion contextual documentada."
        elif protective_profiles:
            effect = guidance.get("protector_effect")
            if effect in {"satisfies_exception", "resolves_omission"}:
                exception_status = "protector_present"
                exception_reason = "Se encontro la coprescripcion protectora en el episodio."
            else:
                exception_status = "mitigation_present_requires_context"
                exception_reason = (
                    "Se encontro un protector, pero el criterio exige confirmar otras condiciones."
                )
        elif guidance.get("protective_group_terms") or guidance.get(
            "protective_name_terms"
        ):
            missing_exception_fields = [
                field
                for field, value in exception_values.items()
                if value is None
            ]
            exception_status = (
                "exception_unknown_and_protector_not_found_in_top_v1"
                if missing_exception_fields
                else "protector_not_found_in_top_v1"
            )
            exception_reason = (
                "No se encontro el protector en los medicamentos del top V1; "
                "confirmar la lista completa."
            )
            if missing_exception_fields:
                labels = ", ".join(
                    FIELD_LABELS.get(field, field)
                    for field in missing_exception_fields
                )
                exception_reason += f" Falta documentar: {labels}."
        elif exception_fields and any(value is None for value in exception_values.values()):
            exception_status = "exception_unknown"
            exception_reason = "Falta documentar si aplica una excepcion del criterio."
        elif exception_fields:
            exception_status = "exception_not_met"
            exception_reason = "Las excepciones documentadas no se cumplen."
        else:
            exception_status = "not_applicable"
            exception_reason = None

        actions = list(guidance.get("actions", []))
        for field in missing_fields:
            action = f"Obtener o confirmar: {FIELD_LABELS.get(field, field)}."
            if action not in actions:
                actions.append(action)
        if not actions:
            actions.append(
                "Revisar el criterio y la farmacoterapia con el equipo clinico antes de realizar cambios."
            )

        logic_summary = precondition_reason or reason
        return {
            "triggering_evidence": triggering,
            "protective_evidence": protective,
            "exception_status": exception_status,
            "exception_reason": exception_reason,
            "recommended_actions": actions,
            "logic_summary": logic_summary,
            "medication_coverage_note": (
                "La evaluacion automatica solo conoce los medicamentos del top V1 activos en la fecha indice; "
                "la ausencia de un farmaco protector o interactuante debe confirmarse contra la lista completa."
            ),
        }

    @staticmethod
    def _evaluate_automated(
        code: str,
        context: dict[str, Any],
        present_names: list[str],
        present_groups: list[str],
        implicated_medications: list[str] | None = None,
    ) -> bool:
        names = [_canonical(item) for item in present_names]
        groups = [_canonical(item) for item in present_groups]
        has_name = lambda *needles: any(
            any(_canonical(needle) in name for needle in needles) for name in names
        )
        has_group = lambda needle: any(_canonical(needle) in group for group in groups)
        count_group = lambda needle: sum(
            _canonical(needle) in group for group in groups
        )
        has_aine = has_group("ANTIINFLAMATORIO NO ESTEROIDEO")
        has_opioid = has_group("OPIOIDE")
        has_benzo = has_group("BENZODIACEPINA")
        has_gabapentinoid = has_name("GABAPENTINA", "PREGABALINA")
        has_ppi = has_group("BOMBA DE PROTONES")
        has_laxative = has_group("LAXANTE")
        has_raas = lambda: sum(
            any(token in group for token in ("ARA II", "IECA", "ARNI"))
            for group in groups
        )

        if code in {"B01", "B02", "B03", "B10", "STOPP-J1"}:
            return True
        if code == "B05":
            duration_days = ClinicalCatalogService._context_value(
                "medication_duration_days",
                context,
                groups,
                implicated_medications,
            )
            high_risk_companion = any(
                has_group(group)
                for group in (
                    "CORTICOIDE SISTEMICO",
                    "ANTICOAGULANTE",
                    "ANTIAGREGANTE",
                )
            )
            exception_complete = bool(
                context.get("safer_alternatives_ineffective")
            ) and bool(
                ClinicalCatalogService._context_value(
                    "gastroprotection", context, groups, implicated_medications
                )
            )
            return (
                duration_days > CHRONIC_AINE_DAYS_V1 or high_risk_companion
            ) and not exception_complete
        if code == "B07":
            exception_complete = bool(
                context.get("safer_alternatives_ineffective")
            ) and bool(
                ClinicalCatalogService._context_value(
                    "gastroprotection", context, groups, implicated_medications
                )
            )
            return bool(context["peptic_ulcer_history"]) and not exception_complete
        if code == "B08":
            return has_aine and context["egfr_ml_min_1_73m2"] < 30
        if code == "B15":
            return has_opioid and has_benzo
        if code == "B16":
            return (
                has_opioid
                and has_gabapentinoid
                and not bool(context.get("opioid_transition_or_dose_reduction"))
            )
        if code == "B17":
            cns_terms = (
                "ANTICONVULSIVANTE",
                "BENZODIACEPINA",
                "OPIOIDE",
                "RELAJANTE MUSCULAR",
                "ANTIDEPRESIVO",
                "ANTIPSICOTICO",
            )
            return sum(any(term in group for term in cns_terms) for group in groups) >= 3
        if code in {"B18", "STOPP-M1"}:
            return count_group("RELAJANTE MUSCULAR") >= 2
        if code == "B19":
            return has_name("GABAPENTINA") and context["egfr_ml_min_1_73m2"] < 60
        if code == "B20":
            return has_name("TRAMADOL") and context["egfr_ml_min_1_73m2"] < 30
        if code == "B21":
            return context["egfr_ml_min_1_73m2"] < 60 and has_raas() >= 2
        if code == "B22":
            return (
                has_name("LITIO")
                and has_raas() >= 1
                and not bool(context.get("lithium_level_monitoring"))
            )
        if code == "STOPP-A3":
            return any(count >= 2 for count in Counter(groups).values())
        if code == "STOPP-B3":
            return has_group("BETABLOQUEADOR") and has_name("VERAPAMILO", "DILTIAZEM")
        if code == "STOPP-B12":
            return has_raas() >= 1 and context["potassium_mmol_l"] > 5.5
        if code == "STOPP-B13":
            return not bool(context["potassium_monitoring"])
        if code == "STOPP-C4":
            return bool(context["atrial_fibrillation"]) and not bool(
                context["coronary_stent_or_stenosis"]
            )
        if code == "STOPP-C10":
            return has_aine and has_group("ANTICOAGULANTE")
        if code == "STOPP-C14":
            return has_name("AZITROMICINA") and has_name(
                "APIXABAN", "DABIGATRAN", "EDOXABAN", "RIVAROXABAN"
            )
        if code == "STOPP-D8":
            return has_benzo and ClinicalCatalogService._context_value(
                "medication_duration_days",
                context,
                groups,
                implicated_medications,
            ) >= 28
        if code == "STOPP-E4":
            return has_aine and context["egfr_ml_min_1_73m2"] < 50
        if code == "STOPP-E6":
            return has_name("METFORMINA") and context["egfr_ml_min_1_73m2"] < 30
        if code == "STOPP-E9":
            return has_group("BISFOSFONATO") and context["egfr_ml_min_1_73m2"] < 30
        if code == "STOPP-F5":
            return bool(context["peptic_ulcer_history"]) and not bool(
                ClinicalCatalogService._context_value(
                    "gastroprotection", context, groups, implicated_medications
                )
            )
        if code == "STOPP-H1":
            return has_aine and bool(context["peptic_ulcer_history"]) and not bool(
                ClinicalCatalogService._context_value(
                    "gastroprotection", context, groups, implicated_medications
                )
            )
        if code == "STOPP-H2":
            return has_aine and (
                context["systolic_bp_mm_hg"] > 170
                or context["diastolic_bp_mm_hg"] > 100
            )
        if code == "STOPP-H3":
            duration_days = ClinicalCatalogService._context_value(
                "medication_duration_days",
                context,
                groups,
                implicated_medications,
            )
            return (
                has_aine
                and duration_days > 90
                and bool(context["osteoarthritis"])
                and not bool(context["prior_paracetamol_trial"])
            )
        if code == "STOPP-H7":
            return has_aine and has_group("CORTICOIDE SISTEMICO")
        if code == "STOPP-J9":
            return (
                has_name("LEVOTIROXINA")
                and bool(context["free_t4_normal"])
                and 0 < context["tsh_miu_l"] < 10
            )
        if code == "STOPP-L2":
            return has_opioid and bool(context["opioid_regular_use"]) and not has_laxative
        if code == "STOPP-L6":
            daily_dose = ClinicalCatalogService._context_value(
                "daily_dose_mg", context, groups, implicated_medications
            )
            return has_name("PARACETAMOL") and daily_dose >= 3000 and (
                context["bmi"] < 18 or bool(context["chronic_liver_disease"])
            )
        if code == "START-B1":
            frailty = str(context["frailty_status"]).lower()
            threshold = 150 if frailty in {"moderate", "severe", "moderada", "grave"} else 140
            return (
                context["systolic_bp_mm_hg"] > threshold
                or context["diastolic_bp_mm_hg"] > 90
            ) and not (
                has_group("ANTIHIPERTENSIVO")
                or has_group("ARA II")
                or has_group("IECA")
            )
        if code == "START-F3":
            return has_aine and not has_ppi
        if code == "START-H9":
            return has_name("METOTREXATO") and not has_name("ACIDO FOLICO")
        if code == "START-K2":
            return has_opioid and bool(context["opioid_regular_use"]) and not has_laxative
        return False

    def evaluate(
        self,
        medications: list[Any],
        *,
        age: int,
        sex: str,
        clinical_context: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        catalog = self._load_catalog()
        context = dict(clinical_context or {})
        context.setdefault("sex", sex)
        input_names = [self._medication_name(item) for item in medications]
        input_presentations = [
            self._entered_medication_name(item) for item in medications
        ]

        matched_rows: list[dict[str, Any]] = []
        for input_index, input_name in enumerate(input_names):
            for item in catalog["medications"]:
                if self._matches(input_name, item["medication"]):
                    matched_rows.append(
                        {
                            **item,
                            "input_index": input_index,
                            "input_medication": input_name,
                            "essi_presentation": input_presentations[input_index],
                            "canonical_group": _canonical(item["pharmacologic_group"]),
                        }
                    )

        unique_matches: dict[tuple[int, str], dict[str, Any]] = {}
        for item in matched_rows:
            key = (item["input_index"], item["medication"])
            unique_matches[key] = item
        matched_rows = list(unique_matches.values())
        criteria_by_code = {item["code"]: item for item in catalog["criteria"]}

        candidate_codes: set[str] = set()
        for item in matched_rows:
            candidate_codes.update(item["beers_codes"])
            candidate_codes.update(item["stopp_codes"])
            candidate_codes.update(item["start_codes"])

        first_match_by_input: dict[int, dict[str, Any]] = {}
        for item in matched_rows:
            first_match_by_input.setdefault(item["input_index"], item)
        present_names = [
            input_names[index] for index in sorted(first_match_by_input)
        ]
        present_groups = [
            first_match_by_input[index]["canonical_group"]
            for index in sorted(first_match_by_input)
        ]
        results: list[dict[str, Any]] = []
        alerts: list[dict[str, Any]] = []

        for code in sorted(candidate_codes):
            criterion = criteria_by_code.get(code)
            if not criterion:
                continue
            implicated = sorted(
                {
                    item["input_medication"]
                    for item in matched_rows
                    if code
                    in (
                        item["beers_codes"]
                        + item["stopp_codes"]
                        + item["start_codes"]
                    )
                }
            )
            medication_classification = []
            seen_classifications: set[tuple[str, str]] = set()
            for item in matched_rows:
                if code not in (
                    item["beers_codes"]
                    + item["stopp_codes"]
                    + item["start_codes"]
                ):
                    continue
                key = (item["essi_presentation"], item["medication"])
                if key in seen_classifications:
                    continue
                seen_classifications.add(key)
                medication_classification.append(
                    {
                        "essi_presentation": item["essi_presentation"],
                        "evaluation_name": item["input_medication"],
                        "catalog_medication": item["medication"],
                        "pharmacologic_group": item["pharmacologic_group"],
                    }
                )
            required_fields = list(REQUIREMENTS.get(code, ()))
            context_used = {
                field: self._context_value(
                    field, context, present_groups, implicated
                )
                for field in required_fields
                if _present(
                    self._context_value(
                        field, context, present_groups, implicated
                    )
                )
            }
            lab_evidence = [
                item
                for item in (context.get("lab_provenance") or [])
                if item.get("field") in required_fields and item.get("applied")
            ]
            diagnosis_evidence = [
                item
                for item in (context.get("diagnosis_provenance") or [])
                if (
                    item.get("field") in required_fields
                    or set(item.get("related_fields") or []).intersection(
                        required_fields
                    )
                )
            ]
            missing_fields = [
                field
                for field in required_fields
                if not _present(
                    self._context_value(
                        field, context, present_groups, implicated
                    )
                )
            ]

            precondition_met, precondition_reason = self._medication_precondition(
                code, present_names, present_groups
            )
            effective_missing_fields = (
                [] if precondition_met is False else missing_fields
            )

            if precondition_met is False:
                status = CATALOG_STATUS_NO_ALERT
                reason = precondition_reason or (
                    "No se encontró la exposición farmacológica requerida por el criterio."
                )
            elif effective_missing_fields:
                status = CATALOG_STATUS_NOT_EVALUABLE
                reason = "Faltan datos obligatorios para completar el criterio."
            elif code in AUTOMATED_CODES:
                triggered = self._evaluate_automated(
                    code,
                    context,
                    present_names,
                    present_groups,
                    implicated,
                )
                status = (
                    CATALOG_STATUS_ALERT if triggered else CATALOG_STATUS_NO_ALERT
                )
                reason = (
                    "El tamizaje automático V1 encontró la condición."
                    if triggered
                    else "La condición automática V1 no se encontró."
                )
            else:
                status = CATALOG_STATUS_MANUAL_REVIEW
                reason = (
                    "El medicamento coincide con el catálogo, pero este criterio "
                    "requiere interpretación clínica o una regla aún no automatizada."
                )

            logic_details = self._logic_details(
                code,
                status=status,
                reason=reason,
                context=context,
                present_names=present_names,
                present_groups=present_groups,
                implicated=implicated,
                missing_fields=effective_missing_fields,
                precondition_reason=(
                    precondition_reason if precondition_met is False else None
                ),
            )

            result = {
                "criterion_code": code,
                "system": criterion["system"],
                "criterion_type": criterion["type"],
                "status": status,
                "statement": criterion["statement"],
                "source_location": criterion["location"],
                "implicated_medications": implicated,
                "medication_classification": medication_classification,
                "missing_data": [
                    {
                        "field": field,
                        "label": FIELD_LABELS.get(field, field),
                    }
                    for field in effective_missing_fields
                ],
                "reason": reason,
                "catalog_version": catalog["catalog_version"],
                "age_scope": (
                    "protocol_adaptation_60_64"
                    if criterion["system"] == "beers" and age < 65
                    else "standard_65_plus"
                    if criterion["system"] == "beers"
                    else "pilot_60_plus"
                ),
                "context_used": context_used,
                "lab_evidence": lab_evidence,
                "diagnosis_evidence": diagnosis_evidence,
                **logic_details,
            }
            results.append(result)

            if status == CATALOG_STATUS_ALERT:
                alerts.append(
                    {
                        "rule_code": code,
                        "alert_type": f"tamizaje {criterion['type']} V1",
                        "severity": "advertencia",
                        "problem_identified": criterion["statement"],
                        "recommendation": " ".join(
                            logic_details["recommended_actions"]
                        ),
                        "justification": reason,
                        "source": (
                            f"{catalog['source_file']} - {criterion['location']}"
                        ),
                        "rule_version": catalog["catalog_version"],
                        "is_demo": False,
                        "analysis_system": criterion["system"],
                        "implicated_medications": implicated,
                        "trace_data": {
                            "condition_evaluated": code,
                            "input_count": len(input_names),
                            "normalized_medications": input_names,
                            "implicated_medications": implicated,
                            "medication_classification": medication_classification,
                            "rule_code": code,
                            "rule_version": catalog["catalog_version"],
                            "analysis_system": criterion["system"],
                            "criterion_status": status,
                            "age_scope": result["age_scope"],
                            "context_used": context_used,
                            "lab_evidence": lab_evidence,
                            "diagnosis_evidence": diagnosis_evidence,
                            "triggering_evidence": logic_details[
                                "triggering_evidence"
                            ],
                            "protective_evidence": logic_details[
                                "protective_evidence"
                            ],
                            "exception_status": logic_details[
                                "exception_status"
                            ],
                            "exception_reason": logic_details[
                                "exception_reason"
                            ],
                            "recommended_actions": logic_details[
                                "recommended_actions"
                            ],
                            "logic_summary": logic_details["logic_summary"],
                            "medication_coverage_note": logic_details[
                                "medication_coverage_note"
                            ],
                        },
                    }
                )

        return alerts, results
