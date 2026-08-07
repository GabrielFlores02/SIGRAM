"""Regenera los reportes derivados de la muestra usando la API vigente."""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.database import Base, get_db
from backend.app.main import app


SAMPLE_DIR = ROOT / "data" / "processed" / "v1_handoff"
REPORT_PATH = SAMPLE_DIR / "sample_criterion_reports.json"
SUMMARY_PATH = SAMPLE_DIR / "sample_summary.csv"
MANIFEST_PATH = SAMPLE_DIR / "manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=engine
    )
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    reports: list[dict] = []
    summary_rows: list[dict] = []
    try:
        with TestClient(app) as client:
            patients_response = client.get("/api/pilot/v1/sample-patients")
            patients_response.raise_for_status()
            for patient in patients_response.json():
                response = client.post(
                    "/api/pilot/v1/sample-patients/"
                    f"{patient['patient_code']}/evaluate",
                    json={},
                )
                response.raise_for_status()
                payload = response.json()
                evaluation = payload["evaluation"]
                availability = payload["data_availability"]
                technical_report = evaluation["criteria_report"]
                clinical_findings = evaluation["clinical_findings"]
                data_gaps = evaluation["data_gaps"]
                assert all(
                    item["status"] == "alert" for item in clinical_findings
                )
                reports.append(
                    {
                        "patient_code": patient["patient_code"],
                        "age": patient["age"],
                        "sex": patient["sex"],
                        "medication_index_date": availability[
                            "medication_index_date"
                        ],
                        "clinical_observation_start_date": availability[
                            "clinical_observation_start_date"
                        ],
                        "clinical_observation_end_date": availability[
                            "clinical_observation_end_date"
                        ],
                        "medication_catalog_classification": availability[
                            "medication_catalog_classification"
                        ],
                        "criteria_report": technical_report,
                        "clinical_findings": clinical_findings,
                        "data_gaps": data_gaps,
                        "manual_review_findings": evaluation[
                            "manual_review_findings"
                        ],
                        "analysis_results": evaluation["analysis_results"],
                        "note": (
                            "criteria_report conserva el analisis tecnico completo; "
                            "clinical_findings es la vista principal para frontend. "
                            "CIE-10 y examenes se observan durante todo 2025."
                        ),
                    }
                )
                summary_rows.append(
                    {
                        "patient_code": patient["patient_code"],
                        "age": patient["age"],
                        "sex": patient["sex"],
                        "medications_active_at_index": availability[
                            "medications_loaded"
                        ],
                        "medication_index_date": availability[
                            "medication_index_date"
                        ],
                        "visible_clinical_alerts": len(clinical_findings),
                        "criteria_requiring_additional_data": len(data_gaps),
                    }
                )
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()

    REPORT_PATH.write_text(
        json.dumps(reports, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    with SUMMARY_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_rows[0]))
        writer.writeheader()
        writer.writerows(summary_rows)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    manifest["created_at"] = datetime.now(UTC).isoformat()
    for path in (REPORT_PATH, SUMMARY_PATH):
        entry = next(
            item for item in manifest["files"] if item["name"] == path.name
        )
        entry["bytes"] = path.stat().st_size
        entry["sha256"] = sha256_file(path)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"patients={len(reports)}")
    print(
        "visible_clinical_alerts="
        f"{sum(len(item['clinical_findings']) for item in reports)}"
    )


if __name__ == "__main__":
    main()
