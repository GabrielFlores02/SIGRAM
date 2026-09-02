"""Precalcula el ranking clínico de los 200 candidatos Rebagliati 2025."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.rebagliati_population_service import (
    RebagliatiPopulationService,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    service = RebagliatiPopulationService()
    page = service._list_engine_ranked_patients(
        offset=0, limit=200, query=None, candidate_limit=200
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_scope": page["ranking_scope"],
        "candidate_count": page["total"],
        "items": page["items"],
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": str(output),
                "candidate_count": payload["candidate_count"],
                "top_patient": payload["items"][0]["patient_code"],
                "top_alerts": payload["items"][0]["engine_alert_count"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
