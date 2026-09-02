"""Consulta bajo demanda de la cohorte Rebagliati 2025.

Los Parquet de la entrega son demasiado grandes para ser cargados con Polars en
cada petición. DuckDB aplica el filtro ``patient_code`` al escaneo Parquet y
solo materializa las filas del paciente solicitado.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import polars as pl
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.app.services.clinical_catalog_service import ClinicalCatalogService
from backend.app.services.ddinter_csv_provider import DDInterCsvProvider
from backend.app.services.pilot_sample_service import PilotSampleService


class RebagliatiPopulationService(PilotSampleService):
    """Implementa el mismo contrato clínico que el piloto para toda la cohorte."""

    diagnosis_source_label = "diagnoses_rebagliati_2025.parquet"
    population_note = (
        "Cohorte Rebagliati 2025. Los laboratorios y CIE-10 se consultan por "
        "patient_code; la ausencia de una fila de laboratorio no representa un "
        "resultado normal ni la ausencia de una condición clínica. Beers y "
        "STOPP/START están habilitados como tamizaje de investigación y requieren "
        "interpretación y validación clínica."
    )
    _engine_ranking_cache: list[dict] | None = None
    _simple_patients_cache: list[dict] | None = None
    _preferred_simple_cie10 = (
        "K29.7",
        "F41.2",
        "K59.0",
        "I25.5",
        "K29.5",
        "F41.9",
        "K21.9",
        "K29.3",
        "I69.3",
        "F06.7",
    )

    def __init__(self) -> None:
        self.patients_path = Path(settings.SIGRAM_PATIENTS_FILE)
        self.medications_path = Path(settings.SIGRAM_MEDICATIONS_FILE)
        self.labs_path = Path(settings.SIGRAM_LABS_FILE)
        self.diagnoses_path = Path(settings.SIGRAM_DIAGNOSES_FILE)
        self.patient_summary_path = Path(settings.SIGRAM_PATIENT_SUMMARY_FILE)
        self.engine_ranking_path = Path(settings.SIGRAM_ENGINE_RANKING_FILE)

    def _require_sources(self) -> None:
        missing = [
            str(path)
            for path in (
                self.patients_path,
                self.medications_path,
                self.labs_path,
                self.diagnoses_path,
                self.patient_summary_path,
            )
            if not path.is_file()
        ]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "message": "Faltan los Parquet de la entrega Rebagliati 2025.",
                    "files": missing,
                },
            )

    @staticmethod
    def _sql_path(path: Path) -> str:
        return str(path.resolve()).replace("'", "''")

    def _query(self, sql: str, params: list[object] | None = None) -> pl.DataFrame:
        self._require_sources()
        with duckdb.connect(database=":memory:", read_only=False) as connection:
            result = connection.execute(sql, params or []).fetch_arrow_table()
        return pl.from_arrow(result)

    def list_patients(
        self,
        *,
        offset: int = 0,
        limit: int = 50,
        query: str | None = None,
        sort: str = "patient_code",
    ) -> dict:
        if sort == "engine_alerts":
            return self._list_engine_ranked_patients(
                offset=offset, limit=limit, query=query
            )
        safe_limit = min(max(limit, 1), settings.SIGRAM_POPULATION_MAX_PAGE_SIZE)
        safe_offset = max(offset, 0)
        patients = self._sql_path(self.patients_path)
        summary = self._sql_path(self.patient_summary_path)
        where = ""
        params: list[object] = []
        if query and query.strip():
            where = "WHERE p.patient_code ILIKE ?"
            params.append(f"%{query.strip()}%")
        count_sql = f"SELECT count(*) AS total FROM read_parquet('{patients}') p {where}"
        total = int(self._query(count_sql, params).item(0, 0))
        order_by = (
            "screening_alert_count DESC, p.patient_code"
            if sort == "alerts"
            else "p.patient_code"
        )
        rows_sql = f"""
            SELECT p.patient_code, p.age, p.sexo AS sex,
                   p.polypharmacy_level,
                   p.max_simultaneous_medications AS max_simultaneous_top_medications,
                   p.beers_screening_flag, p.ddinter_screening_flag,
                   CAST(GREATEST(
                       COALESCE(s.total_grupos_beers_extension_60a64, 0),
                       COALESCE(s.total_grupos_beers_nacional_65plus, 0),
                       COALESCE(s.total_beers_pims, 0)
                   ) AS BIGINT) AS beers_screening_group_count,
                   CAST(COALESCE(s.n_interacciones_ddinter_potenciales, 0) AS BIGINT)
                       AS ddinter_potential_count,
                   CAST(
                       GREATEST(
                           COALESCE(s.total_grupos_beers_extension_60a64, 0),
                           COALESCE(s.total_grupos_beers_nacional_65plus, 0),
                           COALESCE(s.total_beers_pims, 0)
                       ) + COALESCE(s.n_interacciones_ddinter_potenciales, 0)
                       AS BIGINT
                   ) AS screening_alert_count
            FROM read_parquet('{patients}') p
            LEFT JOIN read_parquet('{summary}') s USING (patient_code)
            {where}
            ORDER BY {order_by}
            LIMIT ? OFFSET ?
        """
        rows = self._query(rows_sql, [*params, safe_limit, safe_offset]).to_dicts()
        for row in rows:
            row["index_date"] = None
            # Estos contadores se consultan en el detalle; no se agregan sobre
            # millones de filas cada vez que se pagina el directorio.
            row["distinct_top_medications_2025"] = int(
                row.get("max_simultaneous_top_medications") or 0
            )
            row["medication_rows_2025"] = None
            row["raw_lab_rows_2025"] = None
            row["raw_diagnosis_rows_2025"] = None
            row["distinct_diagnosis_codes_2025"] = None
        return {"items": rows, "total": total, "offset": safe_offset, "limit": safe_limit}

    def list_simple_patients(
        self, *, query: str | None = None, limit: int = 50
    ) -> dict:
        """Combina ejemplos sin polifarmacia y pacientes priorizados por el motor."""
        safe_limit = min(max(limit, 1), settings.SIGRAM_POPULATION_MAX_PAGE_SIZE)
        normalized_query = (query or "").strip()
        if normalized_query:
            page = self.list_patients(
                offset=0,
                limit=safe_limit,
                query=normalized_query,
                sort="patient_code",
            )
            items = page["items"]
            for item in items:
                item["simple_example_group"] = "search"
                item["estimated_alert_count"] = item.get("screening_alert_count")
            self._attach_example_diagnoses(items)
            return {**page, "items": items}

        if self.__class__._simple_patients_cache is None:
            nonpoly = self._list_nonpolypharmacy_examples(limit=20)
            prioritized = self._list_engine_ranked_patients(
                offset=0, limit=30, query=None
            )["items"]
            for item in prioritized:
                item["simple_example_group"] = "prioritized"
                item["estimated_alert_count"] = item.get("engine_alert_count")
            self._attach_example_diagnoses(prioritized)
            seen: set[str] = set()
            combined = []
            for item in [*nonpoly, *prioritized]:
                if item["patient_code"] in seen:
                    continue
                seen.add(item["patient_code"])
                combined.append(item)
            self.__class__._simple_patients_cache = combined

        items = self.__class__._simple_patients_cache[:safe_limit]
        return {
            "items": items,
            "total": len(self.__class__._simple_patients_cache),
            "offset": 0,
            "limit": safe_limit,
        }

    def _list_nonpolypharmacy_examples(self, *, limit: int) -> list[dict]:
        patients = self._sql_path(self.patients_path)
        diagnoses = self._sql_path(self.diagnoses_path)
        summary = self._sql_path(self.patient_summary_path)
        values = ", ".join(
            f"('{code}', {position})"
            for position, code in enumerate(self._preferred_simple_cie10, start=1)
        )
        rows = self._query(
            f"""
            WITH preferred(code, display_order) AS (VALUES {values}),
            candidates AS (
                SELECT DISTINCT p.patient_code, p.age, p.sexo AS sex,
                       p.polypharmacy_level,
                       p.max_simultaneous_medications AS max_simultaneous_top_medications,
                       p.beers_screening_flag, p.ddinter_screening_flag,
                       d.diagnosis_code AS example_cie10_code,
                       preferred.display_order,
                       CAST(
                           GREATEST(
                               COALESCE(s.total_grupos_beers_extension_60a64, 0),
                               COALESCE(s.total_grupos_beers_nacional_65plus, 0),
                               COALESCE(s.total_beers_pims, 0)
                           ) + COALESCE(s.n_interacciones_ddinter_potenciales, 0)
                           AS BIGINT
                       ) AS screening_alert_count
                FROM read_parquet('{patients}') p
                JOIN read_parquet('{diagnoses}') d USING (patient_code)
                JOIN preferred ON upper(trim(d.diagnosis_code)) = preferred.code
                LEFT JOIN read_parquet('{summary}') s USING (patient_code)
                WHERE p.polypharmacy_level = '0-4'
            ), ranked AS (
                SELECT *, row_number() OVER (
                    PARTITION BY example_cie10_code
                    ORDER BY max_simultaneous_top_medications DESC,
                             screening_alert_count DESC, patient_code
                ) AS code_rank
                FROM candidates
            )
            SELECT * EXCLUDE (display_order, code_rank)
            FROM ranked
            WHERE code_rank <= 2
            ORDER BY display_order, code_rank
            LIMIT ?
            """,
            [limit],
        ).to_dicts()
        catalog = ClinicalCatalogService()
        for item in rows:
            item.update(
                {
                    "index_date": None,
                    "distinct_top_medications_2025": int(
                        item.get("max_simultaneous_top_medications") or 0
                    ),
                    "medication_rows_2025": None,
                    "raw_lab_rows_2025": None,
                    "raw_diagnosis_rows_2025": None,
                    "distinct_diagnosis_codes_2025": None,
                    "simple_example_group": "without_polypharmacy",
                    "estimated_alert_count": item.get("screening_alert_count"),
                }
            )
            details = catalog.cie10_details(item["example_cie10_code"])
            if details:
                item["example_cie10_description"] = details.get("diagnosis")
                item["example_cie10_syndrome"] = details.get("syndrome")
        return rows

    def _attach_example_diagnoses(self, items: list[dict]) -> None:
        if not items:
            return
        codes = [item["patient_code"] for item in items]
        placeholders = ",".join("?" for _ in codes)
        diagnoses = self._sql_path(self.diagnoses_path)
        diagnosis_rows = self._query(
            f"""SELECT patient_code, upper(trim(diagnosis_code)) AS diagnosis_code
                FROM read_parquet('{diagnoses}')
                WHERE patient_code IN ({placeholders})""",
            codes,
        ).to_dicts()
        by_patient: dict[str, set[str]] = {}
        for row in diagnosis_rows:
            by_patient.setdefault(row["patient_code"], set()).add(
                row["diagnosis_code"]
            )
        catalog = ClinicalCatalogService()
        preferred_order = {
            code: position for position, code in enumerate(self._preferred_simple_cie10)
        }
        for item in items:
            patient_diagnoses = by_patient.get(item["patient_code"], set())
            ordered = sorted(
                patient_diagnoses,
                key=lambda code: (preferred_order.get(code, 999), code),
            )
            for code in ordered:
                details = catalog.cie10_details(code)
                if details:
                    item["example_cie10_code"] = code
                    item["example_cie10_description"] = details.get("diagnosis")
                    item["example_cie10_syndrome"] = details.get("syndrome")
                    break

    def _list_engine_ranked_patients(
        self,
        *,
        offset: int,
        limit: int,
        query: str | None,
        candidate_limit: int = 200,
    ) -> dict:
        """Ordena una preselección anual mediante las alertas del motor activo.

        El resumen anual solo se usa para obtener candidatos. La cifra expuesta
        se recalcula con los medicamentos simultáneos de la fecha índice y los
        catálogos configurados, sin crear casos ni escribir en SQLite.
        """
        safe_limit = min(max(limit, 1), settings.SIGRAM_POPULATION_MAX_PAGE_SIZE)
        safe_offset = max(offset, 0)
        use_cache = candidate_limit == 200 and not (query and query.strip())
        if (
            use_cache
            and self.__class__._engine_ranking_cache is None
            and self.engine_ranking_path.is_file()
        ):
            payload = json.loads(self.engine_ranking_path.read_text(encoding="utf-8"))
            self.__class__._engine_ranking_cache = list(payload.get("items", []))
        if use_cache and self._engine_ranking_cache is not None:
            ranked = self._engine_ranking_cache
        else:
            candidates_page = self.list_patients(
                offset=0,
                limit=min(candidate_limit, settings.SIGRAM_POPULATION_MAX_PAGE_SIZE),
                query=query,
                sort="alerts",
            )
            candidates = candidates_page["items"]
            if not candidates:
                return {"items": [], "total": 0, "offset": safe_offset, "limit": safe_limit}

            patient_codes = [item["patient_code"] for item in candidates]
            placeholders = ",".join("?" for _ in patient_codes)
            medications = self._sql_path(self.medications_path)
            medication_rows = self._query(
                f"""SELECT patient_code, medication, fecha_despacho,
                           duracion_dias, diagnosis_code
                    FROM read_parquet('{medications}')
                    WHERE patient_code IN ({placeholders})""",
                patient_codes,
            )
            catalog = ClinicalCatalogService()
            ddinter = DDInterCsvProvider()
            ranked = []
            relevant_statuses = {"alert", "activated"}
            for patient in candidates:
                code = patient["patient_code"]
                rows = medication_rows.filter(pl.col("patient_code") == code)
                index_date, active = self._select_overlap_episode(rows)
                names = sorted(
                    {
                        self._active_ingredient(str(name))
                        for name in active.get_column("medication").to_list()
                    }
                ) if not active.is_empty() else []
                _, criteria = catalog.evaluate(
                    names,
                    age=int(patient["age"]),
                    sex=str(patient.get("sex") or ""),
                    clinical_context={},
                )
                clinical_counts = {
                    system: sum(
                        1
                        for item in criteria
                        if item["system"] == system
                        and item["status"] in relevant_statuses
                    )
                    for system in ("beers", "stopp_start")
                }
                ddinter_count = len(ddinter.find_interactions(names))
                patient.update(
                    {
                        "index_date": index_date.isoformat() if index_date else None,
                        "engine_alert_count": (
                            clinical_counts["beers"]
                            + clinical_counts["stopp_start"]
                            + ddinter_count
                        ),
                        "engine_beers_alert_count": clinical_counts["beers"],
                        "engine_stopp_start_alert_count": clinical_counts["stopp_start"],
                        "engine_ddinter_alert_count": ddinter_count,
                    }
                )
                ranked.append(patient)
            ranked.sort(
                key=lambda item: (
                    -int(item["engine_alert_count"]),
                    -int(item.get("max_simultaneous_top_medications") or 0),
                    item["patient_code"],
                )
            )
            if use_cache:
                self.__class__._engine_ranking_cache = ranked

        return {
            "items": ranked[safe_offset : safe_offset + safe_limit],
            "total": len(ranked),
            "offset": safe_offset,
            "limit": safe_limit,
            "ranking_scope": f"engine_over_top_{candidate_limit}_annual_candidates",
        }

    def patient_summary(self, patient_code: str) -> dict:
        patients = self._sql_path(self.patients_path)
        row = self._query(
            f"""SELECT p.patient_code, p.age, p.sexo AS sex, p.polypharmacy_level,
                       p.max_simultaneous_medications AS max_simultaneous_top_medications,
                       p.beers_screening_flag, p.ddinter_screening_flag,
                       CAST(GREATEST(
                           COALESCE(s.total_grupos_beers_extension_60a64, 0),
                           COALESCE(s.total_grupos_beers_nacional_65plus, 0),
                           COALESCE(s.total_beers_pims, 0)
                       ) AS BIGINT) AS beers_screening_group_count,
                       CAST(COALESCE(s.n_interacciones_ddinter_potenciales, 0) AS BIGINT)
                           AS ddinter_potential_count,
                       CAST(
                           GREATEST(
                               COALESCE(s.total_grupos_beers_extension_60a64, 0),
                               COALESCE(s.total_grupos_beers_nacional_65plus, 0),
                               COALESCE(s.total_beers_pims, 0)
                           ) + COALESCE(s.n_interacciones_ddinter_potenciales, 0)
                           AS BIGINT
                       ) AS screening_alert_count
                FROM read_parquet('{patients}') p
                LEFT JOIN read_parquet('{self._sql_path(self.patient_summary_path)}') s
                    USING (patient_code)
                WHERE p.patient_code = ?""",
            [patient_code],
        )
        if row.is_empty():
            raise HTTPException(status_code=404, detail=f"Paciente '{patient_code}' no encontrado.")
        summary = row.row(0, named=True)
        medications, labs, diagnoses = self._patient_detail_counts(patient_code)
        summary.update(
            {
                "index_date": None,
                "distinct_top_medications_2025": medications[0],
                "medication_rows_2025": medications[1],
                "raw_lab_rows_2025": labs,
                "raw_diagnosis_rows_2025": diagnoses[0],
                "distinct_diagnosis_codes_2025": diagnoses[1],
            }
        )
        return summary

    def _patient_detail_counts(self, patient_code: str) -> tuple[tuple[int, int], int, tuple[int, int]]:
        medications = self._sql_path(self.medications_path)
        labs = self._sql_path(self.labs_path)
        diagnoses = self._sql_path(self.diagnoses_path)
        med = self._query(
            f"SELECT count(DISTINCT medication), count(*) FROM read_parquet('{medications}') WHERE patient_code = ?",
            [patient_code],
        ).row(0)
        lab = int(self._query(
            f"SELECT count(*) FROM read_parquet('{labs}') WHERE patient_code = ?", [patient_code]
        ).item(0, 0))
        diag = self._query(
            f"SELECT count(*), count(DISTINCT diagnosis_code) FROM read_parquet('{diagnoses}') WHERE patient_code = ?",
            [patient_code],
        ).row(0)
        return (int(med[0]), int(med[1])), lab, (int(diag[0]), int(diag[1]))

    def _patient_rows(self, patient_code: str):
        # Cada SELECT está restringido al paciente antes de convertir a Polars.
        patient = self.patient_summary(patient_code)
        medications = self._sql_path(self.medications_path)
        labs = self._sql_path(self.labs_path)
        diagnoses = self._sql_path(self.diagnoses_path)
        return (
            {**patient, "sexo": patient.get("sex")},
            self._query(f"SELECT * FROM read_parquet('{medications}') WHERE patient_code = ?", [patient_code]),
            self._query(f"SELECT * FROM read_parquet('{labs}') WHERE patient_code = ?", [patient_code]),
            self._query(f"SELECT * FROM read_parquet('{diagnoses}') WHERE patient_code = ?", [patient_code]),
        )
