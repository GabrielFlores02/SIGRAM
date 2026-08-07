r"""Lista o evalua pacientes pseudonimizados del piloto mediante la API local.

Ejemplos:
  .venv-local\Scripts\python.exe scripts\try_sample_patients.py --list
  .venv-local\Scripts\python.exe scripts\try_sample_patients.py \
      --patient-code PILOT-011DA2C70400CA24
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app


def _print_patient_table(patients: list[dict]) -> None:
    print(
        "patient_code,age,sex,index_date,max_simultaneous_top_medications,"
        "raw_lab_rows_2025"
    )
    for patient in patients:
        print(
            f"{patient['patient_code']},{patient['age']},{patient['sex']},"
            f"{patient['index_date']},"
            f"{patient['max_simultaneous_top_medications']},"
            f"{patient['raw_lab_rows_2025']}"
        )


def _compact_result(payload: dict) -> dict:
    evaluation = payload["evaluation"]
    clinical_systems = {"beers", "stopp_start", "ddinter"}
    clinical_alerts = [
        {
            "system": alert["analysis_system"],
            "rule_code": alert["rule_code"],
            "severity": alert["severity"],
            "medications": alert["implicated_medications"],
        }
        for alert in evaluation["alerts"]
        if alert["analysis_system"] in clinical_systems
    ]
    return {
        "patient": payload["patient"],
        "case_id": payload["case"]["id"],
        "case_code": payload["case"]["case_code"],
        "analysis_results": evaluation["analysis_results"],
        "criteria_status_counts": dict(
            Counter(item["status"] for item in evaluation["criteria_report"])
        ),
        "clinical_alerts": clinical_alerts,
        "data_availability": payload["data_availability"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prueba pacientes pseudonimizados contra el backend SIGRAM-AM V1."
    )
    parser.add_argument("--list", action="store_true", help="Lista la muestra.")
    parser.add_argument(
        "--patient-code",
        action="append",
        default=[],
        help="Codigo PILOT-... a evaluar; se puede repetir.",
    )
    parser.add_argument(
        "--all", action="store_true", help="Evalua los 10 pacientes de la muestra."
    )
    parser.add_argument(
        "--context-json",
        help="JSON opcional con clinical_context revisado manualmente.",
    )
    parser.add_argument(
        "--index-date",
        help="Fecha indice opcional en formato AAAA-MM-DD; la muestra cubre 2025.",
    )
    args = parser.parse_args()

    context = json.loads(args.context_json) if args.context_json else None
    with TestClient(app) as client:
        response = client.get("/api/pilot/v1/sample-patients")
        response.raise_for_status()
        patients = response.json()

        if args.list or (not args.patient_code and not args.all):
            _print_patient_table(patients)
        selected = (
            [item["patient_code"] for item in patients]
            if args.all
            else args.patient_code
        )
        for patient_code in selected:
            body = {}
            if context is not None:
                body["clinical_context"] = context
            if args.index_date:
                body["index_date"] = args.index_date
            evaluation = client.post(
                f"/api/pilot/v1/sample-patients/{patient_code}/evaluate",
                json=body or None,
            )
            evaluation.raise_for_status()
            print(json.dumps(_compact_result(evaluation.json()), ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()
