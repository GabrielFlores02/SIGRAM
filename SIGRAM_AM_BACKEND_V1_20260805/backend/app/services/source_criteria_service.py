"""Evaluador directo de las 297 filas clínicas entregadas por el médico."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from backend.app.config import settings


def _canonical(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", str(value or ""))
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


def _present(value: Any) -> bool:
    return value is not None and value != "" and value != []


def _compare(value: float, condition: dict[str, Any]) -> bool:
    operator = condition["operator"]
    if operator == "lt":
        return value < float(condition["value"])
    if operator == "lte":
        return value <= float(condition["value"])
    if operator == "gt":
        return value > float(condition["value"])
    if operator == "gte":
        return value >= float(condition["value"])
    if operator == "between":
        return float(condition["min"]) <= value <= float(condition["max"])
    if operator == "outside":
        return value < float(condition["min"]) or value > float(condition["max"])
    raise ValueError(f"Operador clínico no soportado: {operator}")


class SourceCriteriaService:
    """Aplica una regla ejecutable independiente por cada fila del Excel fuente."""

    def __init__(self, catalog_path: str | Path | None = None) -> None:
        self.catalog_path = Path(catalog_path or settings.SOURCE_CRITERIA_297_FILE)
        self.reference_path = Path(settings.REFERENCE_CATALOG_FILE)
        self.cie_mapping_path = Path(settings.CIE10_CONTEXT_MAPPING_FILE)
        self._catalog: dict[str, Any] | None = None
        self._medication_groups: list[tuple[str, str, str]] | None = None

    @staticmethod
    def _normalize_cie10(value: str) -> str | None:
        compact = re.sub(r"[^A-Z0-9]", "", str(value or "").upper())
        if not re.fullmatch(r"[A-Z][0-9]{2}[0-9A-Z]{0,4}", compact):
            return None
        return compact if len(compact) == 3 else f"{compact[:3]}.{compact[3:]}"

    @staticmethod
    def _cie_matches(code: str, pattern: str) -> bool:
        target = str(pattern).upper().strip()
        return code.startswith(target[:-1]) if target.endswith("*") else code == target

    def _context_from_diagnoses(
        self, context: dict[str, Any], diagnoses: str | None
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        enriched = dict(context)
        raw_codes = list(enriched.get("diagnosis_codes") or [])
        raw_codes.extend(re.findall(r"\b[A-Za-z][0-9]{2}(?:[.]?[0-9A-Za-z]{1,4})?\b", diagnoses or ""))
        codes = sorted({code for value in raw_codes if (code := self._normalize_cie10(str(value)))})
        evidence = list(enriched.get("diagnosis_provenance") or [])
        if not codes:
            return enriched, evidence
        mapping = json.loads(self.cie_mapping_path.read_text(encoding="utf-8"))
        for item in mapping.get("mappings", []):
            matched = [code for code in codes if any(self._cie_matches(code, pattern) for pattern in item["patterns"])]
            if not matched:
                continue
            field = item["field"]
            applied = enriched.get(field) is None
            if applied:
                enriched[field] = bool(item.get("value", True))
            evidence.append({
                "field": field,
                "label": item["label"],
                "value": bool(item.get("value", True)),
                "applied": applied,
                "matched_codes": [{"code": code} for code in matched],
                "source_file": "CIE10_MINSA_OFICIAL_REORGANIZADO.xlsx",
                "mapping_version": mapping.get("mapping_version"),
            })
        enriched["diagnosis_codes"] = codes
        enriched["diagnosis_provenance"] = evidence
        return enriched, evidence

    def _load(self) -> dict[str, Any]:
        if self._catalog is None:
            self._catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            criteria = self._catalog.get("criteria", [])
            if len(criteria) != 297 or len({row["source_id"] for row in criteria}) != 297:
                raise ValueError("El catálogo fuente debe contener 297 criterios únicos.")
        return self._catalog

    def _load_medication_groups(self) -> list[tuple[str, str, str]]:
        if self._medication_groups is None:
            payload = json.loads(self.reference_path.read_text(encoding="utf-8"))
            self._medication_groups = [
                (
                    _canonical(item.get("medication")),
                    _canonical(item.get("pharmacologic_group")),
                    str(item.get("pharmacologic_group") or ""),
                )
                for item in payload.get("medications", [])
            ]
        return self._medication_groups

    def summary(self) -> dict[str, Any]:
        catalog = self._load()
        criteria = catalog["criteria"]
        by_type = Counter(row["criterion_type"] for row in criteria)
        return {
            "catalog_version": catalog["catalog_version"],
            "source_file": catalog["source_file"],
            "criterion_count": len(criteria),
            "source_row_count": len(criteria),
            "stopp_count": by_type["STOPP"],
            "start_count": by_type["START"],
            "beers_count": by_type["BEERS"],
            "criteria_by_system": {
                "beers": by_type["BEERS"],
                "stopp_start": by_type["STOPP"] + by_type["START"],
            },
            "automated_criterion_count": len(criteria),
            "manual_review_criterion_count": 0,
            "implementation_basis": "one_executable_rule_per_source_row",
        }

    def criteria_coverage(self, system: str | None = None) -> list[dict[str, Any]]:
        rows = []
        for criterion in self._load()["criteria"]:
            if system and criterion["system"] != system:
                continue
            rows.append({
                "code": criterion["source_id"],
                "system": criterion["system"],
                "criterion_type": criterion["criterion_type"],
                "statement": criterion["description"],
                "source_location": f"Evaluación completa, fila {criterion['sequence']}",
                "automation_status": "implemented_source_rule",
                "required_data": criterion["required_data"],
                "supporting_data": criterion.get("supporting_data", []),
                "source_name": criterion["source_file"] if "source_file" in criterion else self._load()["source_file"],
                "source_year": 2026,
                "source_table": criterion["classification"],
                "source_section": criterion["clinical_area"],
                "operational_formulation": criterion["logic_summary"],
                "recommendation_type": "start_if_indicated" if criterion["criterion_type"] == "START" else "avoid_or_review",
                "recommendation_text": criterion["description"],
                "doctor_review": criterion.get("doctor_review"),
                "doctor_observation": criterion.get("doctor_observation"),
            })
        return rows

    def source_medications_catalog(self) -> list[dict[str, Any]]:
        """Añade al selector principios activos nombrados por las 297 filas."""
        by_name: dict[str, dict[str, Any]] = {}
        for criterion in self._load()["criteria"]:
            for medication in criterion.get("medication_terms", []):
                key = _canonical(medication)
                if not key or key in {"OPIOIDE DE ACCION CORTA"}:
                    continue
                row = by_name.setdefault(key, {
                    "medication": str(medication).strip().upper(),
                    "pharmacologic_group": "Referencia explícita del criterio fuente",
                    "stopp_codes": [],
                    "start_codes": [],
                    "beers_codes": [],
                    "atc_code": None,
                    "pharmacologic_group_level4": None,
                    "mapping_status": "doctor_review_supplement",
                    "catalog_version": self._load()["catalog_version"],
                    "clinical_rules_validated": True,
                    "reference_group_only": False,
                })
                target = {
                    "STOPP": "stopp_codes",
                    "START": "start_codes",
                    "BEERS": "beers_codes",
                }[criterion["criterion_type"]]
                row[target].append(criterion["source_id"])
        output = sorted(by_name.values(), key=lambda item: _canonical(item["medication"]))
        for order, item in enumerate(output, start=1):
            item["order"] = order
        return output

    def _group_for_medication(self, medication_name: str) -> tuple[str, str]:
        canonical_name = _canonical(medication_name)
        best: tuple[int, str, str] | None = None
        for reference_name, reference_group, display_group in self._load_medication_groups():
            if not reference_name:
                continue
            if canonical_name == reference_name or canonical_name in reference_name or reference_name in canonical_name:
                score = min(len(canonical_name), len(reference_name))
                if best is None or score > best[0]:
                    best = (score, reference_group, display_group)
        return (best[1], best[2]) if best else ("", "")

    @staticmethod
    def _medication_name(medication: Any) -> str:
        if isinstance(medication, dict):
            return str(medication.get("normalized_active_ingredient") or medication.get("entered_name") or "")
        return str(
            getattr(medication, "normalized_active_ingredient", None)
            or getattr(medication, "entered_name", "")
        )

    def _medication_records(self, medications: list[Any]) -> list[dict[str, str]]:
        records = []
        for medication in medications:
            name = self._medication_name(medication)
            group, display_group = self._group_for_medication(name)
            records.append({
                "name": name,
                "canonical_name": _canonical(name),
                "canonical_group": group,
                "group": display_group,
            })
        return records

    @staticmethod
    def _fact_map(context: dict[str, Any]) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        for item in context.get("medication_facts", []) or []:
            key = _canonical(item.get("active_ingredient"))
            if key:
                result[key] = item
        return result

    @staticmethod
    def _fact_for(record: dict[str, str], facts: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
        key = record["canonical_name"]
        if key in facts:
            return facts[key]
        candidates = [fact for fact_key, fact in facts.items() if fact_key in key or key in fact_key]
        return candidates[0] if len(candidates) == 1 else None

    @staticmethod
    def _matches_rule_medication(rule: dict[str, Any], record: dict[str, str]) -> bool:
        name = record["canonical_name"]
        group = record["canonical_group"]
        if any(_canonical(term) in name for term in rule.get("medication_terms", [])):
            return True
        if any(_canonical(term) in group for term in rule.get("group_terms", [])):
            return True
        return False

    @staticmethod
    def _matches_exposure(exposure: dict[str, Any], record: dict[str, str]) -> bool:
        name = record["canonical_name"]
        group = record["canonical_group"]
        return (
            any(_canonical(term) in name for term in exposure.get("names", []))
            or any(_canonical(term) in group for term in exposure.get("groups", []))
        )

    def _interaction_records(
        self, rule: dict[str, Any], records: list[dict[str, str]]
    ) -> tuple[bool, list[dict[str, str]]]:
        config = rule.get("interaction_config") or {}
        mode = config.get("mode")
        if mode == "required_sets":
            matched_by_set = [
                [record for record in records if self._matches_exposure(exposure, record)]
                for exposure in config.get("sets", [])
            ]
            matched = {record["canonical_name"]: record for rows in matched_by_set for record in rows}
            return bool(matched_by_set) and all(matched_by_set), list(matched.values())
        if mode == "count":
            matched = [record for record in records if self._matches_exposure(config, record)]
            distinct = {record["canonical_name"] for record in matched}
            return len(distinct) >= int(config.get("minimum", 2)), matched
        matched = self._matched_records(rule, records)
        distinct = {record["canonical_name"] for record in matched}
        return len(distinct) >= int(rule.get("minimum_distinct_exposures", 2)), matched

    def _matched_records(self, rule: dict[str, Any], records: list[dict[str, str]]) -> list[dict[str, str]]:
        return [record for record in records if self._matches_rule_medication(rule, record)]

    @staticmethod
    def _evaluate_numeric_conditions(
        conditions: list[dict[str, Any]], context: dict[str, Any]
    ) -> tuple[bool | None, list[dict[str, Any]], dict[str, Any]]:
        if not conditions:
            return True, [], {}
        missing = []
        values = []
        used = {}
        for condition in conditions:
            field = condition["field"]
            value = context.get(field)
            if not _present(value):
                missing.append({"field": field, "label": condition["label"]})
                continue
            numeric = float(value)
            used[field] = numeric
            values.append((_compare(numeric, condition), condition.get("join", "and")))
        if missing:
            return None, missing, used
        if any(join == "or" for _, join in values):
            return any(value for value, _ in values), [], used
        return all(value for value, _ in values), [], used

    @staticmethod
    def _evaluate_renal(
        renal: dict[str, Any] | None, context: dict[str, Any]
    ) -> tuple[bool | None, list[dict[str, Any]], dict[str, Any]]:
        if not renal:
            return True, [], {}
        metric = renal["metric"]
        value = context.get(metric)
        label = "TFGe (mL/min/1.73 m²)" if metric.startswith("egfr") else "Depuración de creatinina, CrCl (mL/min)"
        if not _present(value):
            return None, [{"field": metric, "label": label}], {}
        numeric = float(value)
        return _compare(numeric, renal), [], {metric: numeric}

    @staticmethod
    def _evaluate_context_conditions(
        conditions: list[dict[str, Any]], context: dict[str, Any]
    ) -> tuple[bool | None, list[dict[str, Any]], dict[str, Any]]:
        if not conditions:
            return True, [], {}
        missing = []
        values = []
        used = {}
        for condition in conditions:
            field = condition["field"]
            value = context.get(field)
            if value is None or value == "":
                missing.append({"field": field, "label": condition["label"]})
                continue
            normalized = bool(value) == bool(condition.get("expected", True))
            values.append((normalized, condition.get("join", "and")))
            used[field] = bool(value)
        if missing and not any(join == "or" and value for value, join in values):
            return None, missing, used
        if any(join == "or" for _, join in values):
            return any(value for value, _ in values), [], used
        return all(value for value, _ in values), [], used

    def _evaluate_special(
        self,
        rule: dict[str, Any],
        records: list[dict[str, str]],
        context: dict[str, Any],
    ) -> tuple[str, list[dict[str, Any]], list[str], str, dict[str, Any]] | None:
        kind = rule["kind"]
        facts = self._fact_map(context)
        if kind == "missing_indication":
            missing, implicated = [], []
            for record in records:
                fact = self._fact_for(record, facts)
                if not fact or not _present(fact.get("indication")):
                    missing.append({"field": "medication_facts.indication", "label": f"Indicación de {record['name']}"})
                elif fact.get("indication_confirmed") is False or _canonical(fact.get("indication")) in {"SIN INDICACION", "NINGUNA"}:
                    implicated.append(record["name"])
            if implicated:
                return "alert", [], implicated, "Se documentó al menos un medicamento sin indicación clínica.", {}
            if missing:
                return "not_evaluable", missing, [], "Falta documentar la indicación por medicamento; no se genera una alerta presunta.", {}
            return "no_alert", [], [], "Todos los medicamentos tienen una indicación documentada.", {}

        if kind == "excess_duration":
            missing, implicated = [], []
            for record in records:
                fact = self._fact_for(record, facts)
                if not fact:
                    missing.append({"field": "medication_facts", "label": f"Duración de {record['name']}"})
                    continue
                duration = fact.get("duration_days")
                maximum = fact.get("recommended_duration_days")
                if not _present(duration) or not _present(maximum):
                    missing.append({"field": "medication_facts.recommended_duration_days", "label": f"Duración usada y máxima de {record['name']}"})
                elif float(duration) > float(maximum):
                    implicated.append(record["name"])
            if implicated:
                return "alert", [], implicated, "La duración registrada supera el máximo recomendado documentado.", {}
            if missing:
                return "not_evaluable", missing, [], "Falta la duración usada o el límite recomendado por medicamento.", {}
            return "no_alert", [], [], "Ninguna duración supera el límite documentado.", {}

        if kind == "duplicate_class":
            groups: dict[str, list[str]] = defaultdict(list)
            missing = []
            for record in records:
                fact = self._fact_for(record, facts)
                if not fact or fact.get("regular_use") is None:
                    missing.append({"field": "medication_facts.regular_use", "label": f"Uso regular o PRN de {record['name']}"})
                    continue
                if fact["regular_use"] and record["canonical_group"]:
                    groups[record["canonical_group"]].append(record["name"])
            duplicated = [names for names in groups.values() if len(set(names)) >= 2]
            if duplicated:
                implicated = sorted({name for names in duplicated for name in names})
                return "alert", [], implicated, "Hay dos o más medicamentos de la misma clase en uso regular; PRN fue excluido.", {}
            if missing:
                return "not_evaluable", missing, [], "Falta distinguir uso regular frente a PRN.", {}
            return "no_alert", [], [], "No se encontró duplicidad regular de clase farmacológica.", {}

        if kind == "co_treatment_omission":
            config = rule["co_treatment_config"]
            primary = [record for record in records if self._matches_exposure(config["primary"], record)]
            if not primary:
                return "no_alert", [], [], f"No se encontró {config['primary_label']}.", {}
            if rule["source_id"] == "STOPP-129":
                long_present = context.get("criterion_stopp_129_long_acting_opioid_present")
                short_present = context.get("criterion_stopp_129_short_acting_opioid_present")
                missing = []
                if long_present is None:
                    missing.append({"field": "criterion_stopp_129_long_acting_opioid_present", "label": "Opioide de acción prolongada presente"})
                if short_present is None:
                    missing.append({"field": "criterion_stopp_129_short_acting_opioid_present", "label": "Opioide de acción corta para dolor irruptivo presente"})
                if missing:
                    return "not_evaluable", missing, [row["name"] for row in primary], "Falta identificar la duración de acción de los opioides.", {}
                if bool(long_present) and not bool(short_present):
                    return "alert", [], [row["name"] for row in primary], "Hay opioide de acción prolongada sin rescate de acción corta.", {
                        "criterion_stopp_129_long_acting_opioid_present": True,
                        "criterion_stopp_129_short_acting_opioid_present": False,
                    }
                return "no_alert", [], [row["name"] for row in primary], "No se cumple la omisión de rescate descrita.", {}

            facts = self._fact_map(context)
            missing = []
            regular_primary = []
            for record in primary:
                fact = self._fact_for(record, facts)
                if not fact or fact.get("regular_use") is None:
                    missing.append({"field": "medication_facts.regular_use", "label": f"Uso regular o PRN de {record['name']}"})
                elif bool(fact["regular_use"]):
                    regular_primary.append(record)
            if missing:
                return "not_evaluable", missing, [row["name"] for row in primary], "Falta distinguir uso regular frente a PRN.", {}
            if not regular_primary:
                return "no_alert", [], [], "El opioide no está documentado como uso regular.", {}
            required = [record for record in records if self._matches_exposure(config["required"], record)]
            if required:
                return "no_alert", [], [row["name"] for row in regular_primary + required], f"Está presente {config['required_label']}.", {}
            return "alert", [], [row["name"] for row in regular_primary], f"Falta {config['required_label']} junto con {config['primary_label']}.", {}
        return None

    def evaluate(
        self,
        medications: list[Any],
        *,
        age: int,
        sex: str,
        clinical_context: dict[str, Any] | Any | None,
        diagnoses: str | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        if hasattr(clinical_context, "model_dump"):
            context = clinical_context.model_dump()
        else:
            context = dict(clinical_context or {})
        context, diagnosis_evidence = self._context_from_diagnoses(context, diagnoses)
        records = self._medication_records(medications)
        alerts: list[dict[str, Any]] = []
        report: list[dict[str, Any]] = []
        catalog = self._load()

        for rule in catalog["criteria"]:
            source_id = rule["source_id"]
            matched = self._matched_records(rule, records)
            implicated = [record["name"] for record in matched]
            missing: list[dict[str, Any]] = []
            context_used: dict[str, Any] = {}
            triggering_evidence: list[dict[str, Any]] = []
            exception_status = "not_applicable"
            exception_reason = None

            if age < int(rule.get("age_min", 65)):
                status = "out_of_scope"
                reason = "El criterio se aplica a personas de 65 años o más."
            else:
                special = self._evaluate_special(rule, records, context)
                if special:
                    status, missing, implicated, reason, context_used = special
                else:
                    kind = rule["kind"]
                    if kind == "interaction":
                        exposure_present, matched = self._interaction_records(rule, records)
                        implicated = [record["name"] for record in matched]
                    else:
                        minimum = int(rule.get("minimum_distinct_exposures", 1))
                        exposure_present = len({item["canonical_name"] for item in matched}) >= minimum
                    presence_field = rule.get("presence_field")
                    if presence_field:
                        if context.get(presence_field) is None:
                            label = next(
                                (item["label"] for item in rule["required_data"] if item["field"] == presence_field),
                                presence_field,
                            )
                            missing.append({"field": presence_field, "label": label})
                        else:
                            exposure_present = bool(context[presence_field])
                            context_used[presence_field] = exposure_present
                    if kind == "omission" and exposure_present:
                        status = "no_alert"
                        reason = "El tratamiento recomendado por la fila ya está presente."
                    elif kind != "omission" and not exposure_present:
                        status = "no_alert"
                        reason = "No se encontró la exposición farmacológica descrita."
                    else:
                        rule_context = dict(context)
                        if not _present(rule_context.get("daily_dose_mg")):
                            facts = self._fact_map(context)
                            doses = []
                            for record in matched:
                                fact = self._fact_for(record, facts)
                                if fact and _present(fact.get("daily_dose_mg")):
                                    doses.append(float(fact["daily_dose_mg"]))
                            if doses:
                                rule_context["daily_dose_mg"] = max(doses)
                        renal_result, renal_missing, renal_used = self._evaluate_renal(rule.get("renal_condition"), rule_context)
                        numeric_result, numeric_missing, numeric_used = self._evaluate_numeric_conditions(rule.get("structured_conditions", []), rule_context)
                        context_result, context_missing, context_condition_used = self._evaluate_context_conditions(rule.get("context_conditions", []), rule_context)
                        missing.extend(renal_missing)
                        missing.extend(numeric_missing)
                        missing.extend(context_missing)
                        context_used.update(renal_used)
                        context_used.update(numeric_used)
                        context_used.update(context_condition_used)

                        condition_result: bool | None = True
                        condition_field = rule.get("condition_field")
                        if condition_field:
                            value = context.get(condition_field)
                            if value is None or value == "":
                                condition_result = None
                                label = next((item["label"] for item in rule["required_data"] if item["field"] == condition_field), condition_field)
                                missing.append({"field": condition_field, "label": label})
                            else:
                                condition_result = bool(value)
                                context_used[condition_field] = bool(value)

                        if missing or renal_result is None or numeric_result is None or context_result is None or condition_result is None:
                            status = "not_evaluable"
                            reason = "Faltan datos explícitos de esta fila; el motor no presume el resultado."
                        elif not (renal_result and numeric_result and context_result and condition_result):
                            status = "no_alert"
                            reason = "Los datos registrados no cumplen todas las condiciones de la fila."
                        else:
                            exception_field = rule.get("exception_field")
                            if exception_field:
                                exception_value = context.get(exception_field)
                                if exception_value is None or exception_value == "":
                                    label = next((item["label"] for item in rule["required_data"] if item["field"] == exception_field), exception_field)
                                    missing.append({"field": exception_field, "label": label})
                                    status = "not_evaluable"
                                    reason = "Falta confirmar si aplica la excepción explícita del criterio."
                                    exception_status = "unknown"
                                elif bool(exception_value):
                                    status = "no_alert"
                                    reason = "La excepción explícita del criterio fue confirmada."
                                    exception_status = "applies"
                                    exception_reason = reason
                                else:
                                    status = "activated" if kind == "omission" else "alert"
                                    reason = "Se cumplen la exposición/omisión y todas las condiciones descritas en la fila."
                                    exception_status = "does_not_apply"
                            else:
                                status = "activated" if kind == "omission" else "alert"
                                reason = "Se cumplen la exposición/omisión y todas las condiciones descritas en la fila."

            for field, value in context_used.items():
                label = next(
                    (item["label"] for item in rule["required_data"] if item["field"] == field),
                    field,
                )
                triggering_evidence.append({"field": field, "value": value, "label": label})

            result = {
                "criterion_code": source_id,
                "system": rule["system"],
                "criterion_type": rule["criterion_type"],
                "status": status,
                "statement": rule["description"],
                "source_location": f"Evaluación completa, fila {rule['sequence']}",
                "implicated_medications": implicated,
                "medication_classification": [
                    {"medication": record["name"], "pharmacologic_group": record["group"]}
                    for record in matched
                ],
                "missing_data": missing,
                "reason": reason,
                "catalog_version": catalog["catalog_version"],
                "age_scope": "65+",
                "context_used": context_used,
                "lab_evidence": context.get("lab_provenance", []),
                "diagnosis_evidence": diagnosis_evidence,
                "triggering_evidence": triggering_evidence,
                "protective_evidence": [],
                "exception_status": exception_status,
                "exception_reason": exception_reason,
                "recommended_actions": ["Revisar la fila fuente con el médico antes de modificar el tratamiento."],
                "logic_summary": rule["logic_summary"],
                "medication_coverage_note": "Catálogo completo y entrada manual; coincidencia por principio activo o grupo farmacológico.",
                "source_name": catalog["source_file"],
                "source_year": 2026,
                "source_version": catalog["catalog_version"],
                "source_table": rule["classification"],
                "source_section": rule["clinical_area"],
                "operational_formulation": rule["logic_summary"],
                "evaluated_situation": rule["description"],
                "recommendation_type": "start_if_indicated" if rule["kind"] == "omission" else "avoid_or_review",
                "recommendation_text": rule["description"],
                "automation_mode": "automatic_with_structured_data",
                "counts_as_clinical_finding": True,
                "trigger_facts": context_used,
                "review_details": [],
            }
            report.append(result)

            if status in {"alert", "activated"}:
                alerts.append({
                    "rule_code": source_id,
                    "alert_type": f"Criterio fuente {rule['criterion_type']}",
                    "problem_identified": rule["description"],
                    "implicated_medications": implicated,
                    "severity": "moderada" if status == "alert" else "advertencia",
                    "recommendation": "Revisar la prescripción con el equipo clínico.",
                    "justification": reason,
                    "source": f"{catalog['source_file']} - fila {rule['sequence']}",
                    "rule_version": catalog["catalog_version"],
                    "is_demo": False,
                    "trace_data": {
                        "analysis_system": rule["system"],
                        "criterion_status": status,
                        "source_criterion_id": source_id,
                        "logic_summary": rule["logic_summary"],
                        "context_used": context_used,
                    },
                })

        return alerts, report
