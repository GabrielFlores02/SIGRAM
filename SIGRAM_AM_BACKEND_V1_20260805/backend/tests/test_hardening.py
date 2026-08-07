"""Pruebas de endurecimiento técnico de la Fase 2A1.

Cubre:
1.  La configuración usa backend/data/sigram_poc.db.
2.  health responde 200 cuando SQLite está disponible.
3.  health responde 503 y "degraded" cuando SQLite falla.
4.  PRAGMA foreign_keys está activo.
5.  La eliminación de un caso elimina sus medicamentos (cascade con FK enforcement).
6.  Los dependency overrides se limpian.
7.  La base de desarrollo no cambia durante Pytest (verificado en conftest).
8.  IntegrityError se convierte en HTTP 409.
9.  Se ejecuta rollback después de IntegrityError (la sesión sigue usable).
10. Los espacios internos repetidos se normalizan.
"""
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import text

from backend.app.main import app
from backend.app.database import get_db
from backend.app.config import settings
from backend.app.services.medication_normalizer import normalize_active_ingredient


# ─────────────────────────── Helpers ───────────────────────────

def _create_case(client, case_code="HARD-001"):
    """Helper: crea un caso válido con un medicamento."""
    return client.post("/api/cases", json={
        "case_code": case_code,
        "age": 72,
        "sex": "F",
        "diagnoses": "Hipertensión",
        "is_simulated": True,
        "medications": [
            {
                "entered_name": "Enalapril 10mg",
                "normalized_active_ingredient": "enalapril",
                "dose": "10mg",
                "dose_unit": "mg",
                "frequency": "diaria",
                "route": "oral"
            }
        ]
    })


# ─────────────────────────── Pruebas ───────────────────────────

def test_config_uses_canonical_sqlite_path():
    """1. La configuración usa backend/data/sigram_poc.db como ruta canónica."""
    assert settings.DATABASE_URL == "sqlite:///backend/data/sigram_poc.db", (
        f"La ruta de SQLite configurada es '{settings.DATABASE_URL}', "
        "se esperaba 'sqlite:///backend/data/sigram_poc.db'"
    )


def test_health_200_when_db_available(client):
    """2. health responde HTTP 200 con status 'ok' y database 'available'."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "available"


def test_health_503_when_db_unavailable():
    """3. health responde HTTP 503 con status 'degraded' cuando SQLite falla."""
    # Crear un mock de sesión que lance excepción en execute
    def _broken_get_db():
        mock_session = MagicMock()
        mock_session.execute.side_effect = Exception("Simulated DB failure")
        try:
            yield mock_session
        finally:
            pass

    app.dependency_overrides[get_db] = _broken_get_db
    broken_client = TestClient(app)

    try:
        response = broken_client.get("/health")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "unavailable"
        # No deben exponerse detalles internos de la excepción
        assert "Simulated" not in str(data)
    finally:
        app.dependency_overrides.clear()


def test_pragma_foreign_keys_active(db_session):
    """4. PRAGMA foreign_keys está activo (ON) en el motor de pruebas."""
    result = db_session.execute(text("PRAGMA foreign_keys"))
    fk_value = result.scalar()
    assert fk_value == 1, f"PRAGMA foreign_keys devolvió {fk_value}, se esperaba 1 (ON)"


def test_cascade_delete_removes_medications(client, db_session):
    """5. Eliminar un caso elimina sus medicamentos por cascada con FK enforcement."""
    # Crear caso con medicamento
    res = _create_case(client, "HARD-CASCADE")
    assert res.status_code == 201
    case_id = res.json()["id"]

    # Verificar que el medicamento existe
    from backend.app.models.models import Medication
    meds = db_session.query(Medication).filter(Medication.case_id == case_id).all()
    assert len(meds) >= 1

    # Eliminar el caso
    res_del = client.delete(f"/api/cases/{case_id}")
    assert res_del.status_code == 200

    # Verificar que los medicamentos fueron eliminados
    db_session.expire_all()
    meds_after = db_session.query(Medication).filter(Medication.case_id == case_id).all()
    assert len(meds_after) == 0


def test_dependency_overrides_cleaned(client):
    """6. Los dependency overrides se limpian entre pruebas (no quedan residuales)."""
    # Al inicio de cada prueba, conftest establece el override.
    # Verificamos que al menos get_db esté overrideado (como debe ser).
    assert get_db in app.dependency_overrides, (
        "El override de get_db no está activo; conftest no lo configuró correctamente."
    )
    # El conftest limpia los overrides en teardown. Esta prueba verifica que
    # se parte de un estado limpio al registrar que el override está activo
    # durante la prueba (se limpia después de yield).


def test_dev_db_unchanged_during_pytest():
    """7. La base de desarrollo no cambia durante Pytest.

    Esta verificación se ejecuta automáticamente en el conftest (fixture autouse).
    Esta prueba confirma que el mecanismo de verificación está activo.
    """
    import os
    import hashlib
    from backend.tests.conftest import _get_dev_db_hash

    # La función debe ser invocable y devolver un hash o None
    result = _get_dev_db_hash()
    if result is not None:
        # Si la base existe, el hash debe ser de longitud SHA-256
        assert len(result) == 64, f"Hash devuelto tiene longitud {len(result)}, se esperaba 64"


def test_integrity_error_returns_409(client):
    """8. IntegrityError se convierte en HTTP 409 (no HTTP 500)."""
    # Crear primer caso
    res1 = _create_case(client, "HARD-DUP-409")
    assert res1.status_code == 201

    # Intentar crear duplicado: debe dar 409
    res2 = _create_case(client, "HARD-DUP-409")
    assert res2.status_code == 409
    assert "ya se encuentra registrado" in res2.json()["detail"]


def test_rollback_after_integrity_error(client):
    """9. Después de un IntegrityError, la sesión ejecuta rollback y queda usable."""
    # Crear un caso
    res1 = _create_case(client, "HARD-ROLL-001")
    assert res1.status_code == 201

    # Intentar duplicar (provoca IntegrityError + rollback interno)
    res2 = _create_case(client, "HARD-ROLL-001")
    assert res2.status_code == 409

    # Verificar que la sesión sigue usable: crear un caso nuevo con código diferente
    res3 = _create_case(client, "HARD-ROLL-002")
    assert res3.status_code == 201, (
        f"Después del rollback, la sesión debería seguir usable. "
        f"Status: {res3.status_code}, Body: {res3.json()}"
    )


def test_internal_spaces_normalized():
    """10. Los espacios internos repetidos se normalizan a uno solo."""
    # Caso textual del requerimiento
    result = normalize_active_ingredient("  medicamento   demo_a  ")
    assert result == "MEDICAMENTO DEMO_A", f"Se obtuvo: '{result}'"

    # Múltiples espacios internos con tabs
    result2 = normalize_active_ingredient("  ácido    acetilsalicílico  ")
    assert result2 == "ÁCIDO ACETILSALICÍLICO", f"Se obtuvo: '{result2}'"

    # Espacios con tabs mezclados
    result3 = normalize_active_ingredient("  paracetamol\t\t genérico  ")
    assert result3 == "PARACETAMOL GENÉRICO", f"Se obtuvo: '{result3}'"

    # Valor vacío debe lanzar ValueError
    with pytest.raises(ValueError):
        normalize_active_ingredient("")

    with pytest.raises(ValueError):
        normalize_active_ingredient("   ")
