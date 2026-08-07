"""Proveedor local y determinístico para los CSV descargables de DDInter."""

from __future__ import annotations

import csv
import unicodedata
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List

from backend.app.config import settings
from backend.app.services.interaction_provider import InteractionProvider
from backend.app.services.medication_normalizer import normalize_active_ingredient


LEVEL_TO_SEVERITY = {
    "MAJOR": "alta",
    "MODERATE": "moderada",
    "MINOR": "advertencia",
    "UNKNOWN": "advertencia",
}
LEVEL_PRIORITY = {"UNKNOWN": 0, "MINOR": 1, "MODERATE": 2, "MAJOR": 3}


class DDInterCsvProvider(InteractionProvider):
    """Carga, canoniza y deduplica los ocho archivos locales sin alterarlos."""

    _catalog_cache: dict[str, dict[tuple[str, str], dict[str, Any]]] = {}

    def __init__(
        self,
        data_dir: str | Path | None = None,
        alias_file: str | Path | None = None,
        include_unknown: bool | None = None,
    ) -> None:
        self.data_dir = Path(data_dir or settings.DDINTER_DATA_DIR)
        self.alias_file = Path(alias_file or settings.DDINTER_ALIAS_FILE)
        self.include_unknown = (
            settings.DDINTER_INCLUDE_UNKNOWN
            if include_unknown is None
            else include_unknown
        )
        self.aliases = self._load_aliases()
        self.catalog = self._load_catalog()

    @staticmethod
    def _normalized(value: str) -> str:
        normalized = normalize_active_ingredient(value)
        normalized = unicodedata.normalize("NFKD", normalized)
        return "".join(
            char for char in normalized if not unicodedata.combining(char)
        )

    def _load_aliases(self) -> dict[str, str]:
        aliases: dict[str, str] = {}
        if not self.alias_file.exists():
            return aliases
        with self.alias_file.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                local_name = (row.get("local_active_ingredient") or "").strip()
                ddinter_name = (row.get("ddinter_drug_name") or "").strip()
                if local_name and ddinter_name:
                    aliases[self._normalized(local_name)] = self._normalized(ddinter_name)
        return aliases

    def _load_catalog(self) -> dict[tuple[str, str], dict[str, Any]]:
        paths = sorted(self.data_dir.glob("ddinter_downloads_code_*.csv"))
        signature = "|".join(
            f"{path.name}:{path.stat().st_size}:{path.stat().st_mtime_ns}"
            for path in paths
        )
        cache_key = f"{self.data_dir.resolve()}|{signature}"
        cached = self._catalog_cache.get(cache_key)
        if cached is not None:
            return cached

        catalog: dict[tuple[str, str], dict[str, Any]] = {}
        for path in paths:
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    drug_a = self._normalized(row["Drug_A"])
                    drug_b = self._normalized(row["Drug_B"])
                    if drug_a == drug_b:
                        continue
                    key = tuple(sorted((drug_a, drug_b)))
                    level = (row.get("Level") or "Unknown").strip().upper()
                    candidate = {
                        "ddinter_id_a": row["DDInterID_A"],
                        "ddinter_id_b": row["DDInterID_B"],
                        "level": level,
                        "files": {path.name},
                    }
                    current = catalog.get(key)
                    if current is None:
                        catalog[key] = candidate
                    else:
                        current["files"].add(path.name)
                        if LEVEL_PRIORITY.get(level, 0) > LEVEL_PRIORITY.get(
                            current["level"], 0
                        ):
                            candidate["files"] = current["files"]
                            catalog[key] = candidate

        self._catalog_cache[cache_key] = catalog
        return catalog

    def find_interactions(
        self, normalized_medications: List[str]
    ) -> List[Dict[str, Any]]:
        input_by_catalog_name: dict[str, str] = {}
        for medication in normalized_medications:
            local_name = self._normalized(medication)
            catalog_name = self.aliases.get(local_name, local_name)
            input_by_catalog_name.setdefault(catalog_name, local_name)

        interactions: list[dict[str, Any]] = []
        for catalog_a, catalog_b in combinations(sorted(input_by_catalog_name), 2):
            record = self.catalog.get((catalog_a, catalog_b))
            if record is None:
                continue
            if record["level"] == "UNKNOWN" and not self.include_unknown:
                continue

            level = record["level"]
            implicated = sorted(
                (input_by_catalog_name[catalog_a], input_by_catalog_name[catalog_b])
            )
            interactions.append(
                {
                    "rule_code": (
                        f"DDINTER-{record['ddinter_id_a']}-{record['ddinter_id_b']}"
                    ),
                    "alert_type": "interacción farmacológica DDInter",
                    "severity": LEVEL_TO_SEVERITY.get(level, "advertencia"),
                    "problem_identified": (
                        f"DDInter clasifica la combinación con nivel {level.title()}"
                    ),
                    "recommendation": (
                        "revisar la combinación y confirmar la conducta con un "
                        "profesional; el CSV local no incluye manejo clínico detallado"
                    ),
                    "justification": (
                        "coincidencia exacta de principios activos contra el catálogo "
                        "DDInter local deduplicado"
                    ),
                    "source": "DDInter local, exportación clásica por grupos ATC",
                    "rule_version": "ddinter-local-legacy",
                    "is_demo": False,
                    "analysis_system": "ddinter",
                    "implicated_medications": implicated,
                    "catalog_drugs": [catalog_a, catalog_b],
                    "catalog_ids": [record["ddinter_id_a"], record["ddinter_id_b"]],
                    "catalog_level": level,
                    "catalog_files": sorted(record["files"]),
                }
            )
        return interactions
