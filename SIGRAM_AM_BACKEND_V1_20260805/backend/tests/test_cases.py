"""Pruebas CRUD de casos clínicos simulados y medicamentos.

Todas las pruebas utilizan el conftest.py centralizado:
- Motor SQLite en memoria (no toca backend/data/sigram_poc.db).
- Tablas creadas/destruidas por cada prueba.
- dependency_overrides limpiados automáticamente.
"""
import pytest
from backend.app.models.models import ClinicalCase, Medication


# ─────────────────────────── Pruebas originales (1–10) ───────────────────────────

def test_index_and_health_remain_functional(client):
    """10. GET / y GET /health siguen funcionando correctamente."""
    # Test GET /
    res_index = client.get("/")
    assert res_index.status_code == 200
    data_index = res_index.json()
    assert data_index["name"] == "SIGRAM-AM"
    assert data_index["version"] == "1.0.0"
    assert data_index["warning"] == "No utilizar para decisiones clínicas"

    # Test GET /health
    res_health = client.get("/health")
    assert res_health.status_code == 200
    data_health = res_health.json()
    assert data_health["status"] == "ok"
    assert data_health["database"] == "available"


def test_valid_case_creation(client):
    """1. Creación válida de caso simulado con medicamentos."""
    payload = {
        "case_code": "CASE-100",
        "age": 72,
        "sex": "F",
        "diagnoses": "Hipertensión, Osteoartrosis",
        "is_simulated": True,
        "medications": [
            {
                "entered_name": "Enalapril 10mg",
                "normalized_active_ingredient": "enalapril",
                "dose": "10mg",
                "dose_unit": "mg",
                "frequency": "diaria",
                "duration": "90 días",
                "route": "oral"
            }
        ]
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["case_code"] == "CASE-100"
    assert data["age"] == 72
    assert len(data["medications"]) == 1
    assert data["medications"][0]["normalized_active_ingredient"] == "ENALAPRIL"


def test_reject_under_60(client):
    """2. Rechazo de edad menor de 60 años."""
    payload = {
        "case_code": "CASE-101",
        "age": 59,  # < 60
        "sex": "M",
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
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 422  # Validation error


def test_reject_no_medications(client):
    """3. Rechazo de caso sin medicamentos."""
    payload = {
        "case_code": "CASE-102",
        "age": 60,
        "sex": "M",
        "diagnoses": "Ninguno",
        "is_simulated": True,
        "medications": []  # Vacía
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 422  # Validation error


def test_reject_duplicate_case_code(client):
    """4. Rechazo de case_code duplicado (Conflicto 409)."""
    payload = {
        "case_code": "CASE-DUP",
        "age": 80,
        "sex": "F",
        "diagnoses": "Artritis",
        "is_simulated": True,
        "medications": [
            {
                "entered_name": "Paracetamol 500mg",
                "normalized_active_ingredient": "paracetamol",
                "dose": "500mg",
                "dose_unit": "mg",
                "frequency": "cada 8 horas",
                "route": "oral"
            }
        ]
    }
    # Primera creación
    res1 = client.post("/api/cases", json=payload)
    assert res1.status_code == 201

    # Segunda creación
    res2 = client.post("/api/cases", json=payload)
    assert res2.status_code == 409
    assert "ya se encuentra registrado" in res2.json()["detail"]


def test_get_case_by_id(client):
    """5. Consulta de caso clínico por ID."""
    payload = {
        "case_code": "CASE-200",
        "age": 67,
        "sex": "M",
        "diagnoses": "Gota",
        "is_simulated": True,
        "medications": [
            {
                "entered_name": "Alopurinol 100mg",
                "normalized_active_ingredient": "alopurinol",
                "dose": "100mg",
                "dose_unit": "mg",
                "frequency": "diaria",
                "route": "oral"
            }
        ]
    }
    res_post = client.post("/api/cases", json=payload)
    case_id = res_post.json()["id"]

    res_get = client.get(f"/api/cases/{case_id}")
    assert res_get.status_code == 200
    data = res_get.json()
    assert data["case_code"] == "CASE-200"
    assert data["age"] == 67
    assert len(data["medications"]) == 1


def test_list_cases(client):
    """6. Listado general de casos clínicos."""
    payload1 = {
        "case_code": "CASE-301",
        "age": 65,
        "sex": "M",
        "diagnoses": "D1",
        "is_simulated": True,
        "medications": [
            {"entered_name": "M1", "normalized_active_ingredient": "I1", "dose": "1", "dose_unit": "mg", "frequency": "1", "route": "O"}
        ]
    }
    payload2 = {
        "case_code": "CASE-302",
        "age": 70,
        "sex": "F",
        "diagnoses": "D2",
        "is_simulated": True,
        "medications": [
            {"entered_name": "M2", "normalized_active_ingredient": "I2", "dose": "2", "dose_unit": "mg", "frequency": "2", "route": "O"}
        ]
    }
    client.post("/api/cases", json=payload1)
    client.post("/api/cases", json=payload2)

    response = client.get("/api/cases")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # El endpoint de listado no debería tener medicamentos detallados (usa ClinicalCaseList)
    assert "medications" not in data[0]


def test_get_nonexistent_case(client):
    """7. Caso inexistente devuelve 404."""
    response = client.get("/api/cases/99999")
    assert response.status_code == 404
    assert "no encontrado" in response.json()["detail"]


def test_active_ingredient_normalization(client):
    """8. Normalización del principio activo (mayúsculas y remoción de espacios extremos)."""
    payload = {
        "case_code": "CASE-400",
        "age": 75,
        "sex": "F",
        "diagnoses": "Problema cardíaco",
        "is_simulated": True,
        "medications": [
            {
                "entered_name": "Aspirina protect",
                "normalized_active_ingredient": "   ácido acetilsalicílico   ",  # Espacios y minúsculas
                "dose": "100mg",
                "dose_unit": "mg",
                "frequency": "diaria",
                "route": "oral"
            }
        ]
    }
    response = client.post("/api/cases", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["medications"][0]["normalized_active_ingredient"] == "ÁCIDO ACETILSALICÍLICO"


def test_delete_simulated_case(client):
    """9. Eliminación de caso clínico simulado."""
    payload = {
        "case_code": "CASE-500",
        "age": 68,
        "sex": "M",
        "diagnoses": "Cataratas",
        "is_simulated": True,
        "medications": [
            {
                "entered_name": "Gotas",
                "normalized_active_ingredient": "lubricante",
                "dose": "1 gota",
                "dose_unit": "gota",
                "frequency": "cada 4 horas",
                "route": "oftálmica"
            }
        ]
    }
    res_post = client.post("/api/cases", json=payload)
    case_id = res_post.json()["id"]

    # Borrado
    res_del = client.delete(f"/api/cases/{case_id}")
    assert res_del.status_code == 200
    assert "eliminado exitosamente" in res_del.json()["detail"]

    # Comprobación de que ya no existe (404)
    res_get = client.get(f"/api/cases/{case_id}")
    assert res_get.status_code == 404
